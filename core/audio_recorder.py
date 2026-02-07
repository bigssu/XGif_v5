"""
시스템 오디오 및 마이크 오디오 녹음 모듈
Windows WASAPI loopback을 사용하여 컴퓨터 소리 캡처
마이크 입력 오디오 녹음 지원
"""

import os
import tempfile
import threading
import subprocess
import logging
from typing import Optional, List, Tuple
import numpy as np
from .utils import run_subprocess_silent

logger = logging.getLogger(__name__)

# 오디오 라이브러리 (선택적)
try:
    import sounddevice as sd
    import soundfile as sf
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

# pydub 제거됨 — FFmpeg subprocess로 오디오 병합 처리
HAS_PYDUB = False


class AudioRecorder:
    """시스템 오디오 및 마이크 오디오 녹음기 (Context Manager 지원)
    
    사용 예:
        with AudioRecorder() as recorder:
            recorder.start()
            # ... 녹음 ...
            audio_file = recorder.stop()
    """
    
    def __init__(self, max_buffer_mb: Optional[float] = None):
        self.recording = False
        self.record_system = True  # 시스템 오디오 녹음 여부
        self.record_mic = False    # 마이크 오디오 녹음 여부
        
        # 오디오 버퍼 상한 (메모리 안전성): None = 무제한
        self._max_buffer_bytes: Optional[int] = (
            int(max_buffer_mb * 1024 * 1024) if max_buffer_mb is not None and max_buffer_mb > 0 else None
        )
        self._buffer_limit_reached = False  # 상한 도달 시 True (녹음 중지 유도)
        
        # 버퍼 크기 추적 (O(1) 조회)
        self._audio_buffer_total_bytes: int = 0

        # 시스템 오디오
        self.system_audio_data: List[np.ndarray] = []
        self.system_sample_rate = 44100
        self.system_channels = 2
        self._system_stream = None
        
        # 마이크 오디오
        self.mic_audio_data: List[np.ndarray] = []
        self.mic_sample_rate = 44100
        self.mic_channels = 2
        self._mic_stream = None
        
        self._lock = threading.Lock()
        self._temp_file: Optional[str] = None
        
        # loopback 디바이스 ID
        self._loopback_device = None
        self._mic_device = None
        if HAS_AUDIO:
            self._find_devices()
    
    def __enter__(self):
        """Context Manager 진입"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager 종료"""
        if self.is_recording():
            self.stop()
        self.cleanup()
        return False
    
    def _safe_channels(self, device_info, default: int = 2) -> int:
        """디바이스에서 사용 가능한 채널 수 반환 (0이면 Invalid channels 오류 방지)"""
        if device_info is None:
            return max(1, default)
        ch = int(device_info.get('max_input_channels', 0))
        if ch <= 0:
            return max(1, default)
        return min(ch, 2)
    
    def _find_devices(self):
        """오디오 디바이스 찾기"""
        if not HAS_AUDIO:
            return
        
        try:
            devices = sd.query_devices()
            
            # 시스템 오디오 (loopback) 디바이스 찾기
            for i, device in enumerate(devices):
                name = device['name'].lower()
                if 'loopback' in name or 'stereo mix' in name or 'what u hear' in name:
                    if device['max_input_channels'] > 0:
                        self._loopback_device = i
                        self.system_sample_rate = int(device.get('default_samplerate', 44100))
                        self.system_channels = self._safe_channels(device, 2)
                        break
            
            # 마이크 디바이스 찾기 (기본 입력 장치)
            try:
                default_input = sd.query_devices(kind='input')
                if default_input:
                    self._mic_device = default_input['index']
                    self.mic_sample_rate = int(default_input.get('default_samplerate', 44100))
                    self.mic_channels = self._safe_channels(default_input, 2)
            except Exception:
                pass
                
        except Exception:
            self._loopback_device = None
            self._mic_device = None
    
    def set_record_mic(self, enabled: bool):
        """마이크 오디오 녹음 설정"""
        self.record_mic = enabled
    
    def set_record_system(self, enabled: bool):
        """시스템 오디오 녹음 설정"""
        self.record_system = enabled
    
    def is_available(self) -> bool:
        """오디오 녹음 가능 여부"""
        return HAS_AUDIO
    
    def _current_audio_buffer_bytes(self) -> int:
        """현재 오디오 버퍼 총 바이트 수. 반드시 self._lock 내에서 호출해야 합니다."""
        return self._audio_buffer_total_bytes
    
    def set_max_buffer_mb(self, max_buffer_mb: Optional[float]) -> None:
        """오디오 버퍼 상한 설정 (MB). None이면 무제한."""
        self._max_buffer_bytes = (
            int(max_buffer_mb * 1024 * 1024) if max_buffer_mb is not None and max_buffer_mb > 0 else None
        )
    
    @property
    def buffer_limit_reached(self) -> bool:
        """버퍼 상한에 도달했으면 True (녹음 중지 필요)."""
        return self._buffer_limit_reached
    
    def _system_audio_callback(self, indata, frames, time, status):
        """시스템 오디오 스트림 콜백"""
        if self.recording and self.record_system:
            with self._lock:
                if self._buffer_limit_reached:
                    return
                if self._max_buffer_bytes is not None:
                    if self._current_audio_buffer_bytes() + indata.nbytes > self._max_buffer_bytes:
                        self._buffer_limit_reached = True
                        logger.warning("오디오 버퍼 상한에 도달하여 추가 녹음을 중단합니다.")
                        return
                chunk = indata.copy()
                self.system_audio_data.append(chunk)
                self._audio_buffer_total_bytes += chunk.nbytes

    def _mic_audio_callback(self, indata, frames, time, status):
        """마이크 오디오 스트림 콜백"""
        if self.recording and self.record_mic:
            with self._lock:
                if self._buffer_limit_reached:
                    return
                if self._max_buffer_bytes is not None:
                    if self._current_audio_buffer_bytes() + indata.nbytes > self._max_buffer_bytes:
                        self._buffer_limit_reached = True
                        logger.warning("오디오 버퍼 상한에 도달하여 추가 녹음을 중단합니다.")
                        return
                chunk = indata.copy()
                self.mic_audio_data.append(chunk)
                self._audio_buffer_total_bytes += chunk.nbytes
    
    def start(self) -> bool:
        """오디오 녹음 시작"""
        if not HAS_AUDIO:
            return False
        
        if self.recording:
            return True
        
        try:
            with self._lock:
                self.system_audio_data = []
                self.mic_audio_data = []
                self._buffer_limit_reached = False
            
            # 시스템 오디오 스트림 시작 (채널 수는 사용할 디바이스 기준으로 재확인)
            if self.record_system:
                try:
                    dev = sd.query_devices(self._loopback_device) if self._loopback_device is not None else sd.query_devices(kind='input')
                    ch = self._safe_channels(dev, 2)
                    sr = int(dev.get('default_samplerate', 44100))
                    self._system_stream = sd.InputStream(
                        samplerate=sr,
                        channels=ch,
                        callback=self._system_audio_callback,
                        dtype='float32',
                        device=self._loopback_device,
                    )
                    self._system_stream.start()
                    self.system_sample_rate = sr
                    self.system_channels = ch
                except (OSError, RuntimeError) as e:
                    logger.warning(f"시스템 오디오 스트림 시작 실패 (loopback): {e}")
                    try:
                        dev = sd.query_devices(kind='input')
                        ch = self._safe_channels(dev, 2)
                        sr = int(dev.get('default_samplerate', 44100))
                        self._system_stream = sd.InputStream(
                            samplerate=sr,
                            channels=ch,
                            callback=self._system_audio_callback,
                            dtype='float32',
                        )
                        self._system_stream.start()
                        self.system_sample_rate = sr
                        self.system_channels = ch
                    except (OSError, RuntimeError) as e2:
                        logger.error(f"시스템 오디오 스트림 폴백 실패: {e2}")
                        self._system_stream = None
            
            # 마이크 오디오 스트림 시작 (채널 수는 디바이스 기준으로 재확인)
            # 루프백이 없으면 시스템 스트림이 이미 기본 입력(device=None)을 사용 중 → 같은 디바이스 중복 오픈 시 Invalid channels 등 오류 발생하므로 마이크 스트림은 생략
            if self.record_mic and self._loopback_device is not None:
                try:
                    dev = sd.query_devices(self._mic_device) if self._mic_device is not None else sd.query_devices(kind='input')
                    ch = self._safe_channels(dev, 2)
                    sr = int(dev.get('default_samplerate', 44100))
                    self._mic_stream = sd.InputStream(
                        samplerate=sr,
                        channels=ch,
                        callback=self._mic_audio_callback,
                        dtype='float32',
                        device=self._mic_device,
                    )
                    self._mic_stream.start()
                    self.mic_sample_rate = sr
                    self.mic_channels = ch
                except (OSError, RuntimeError) as e:
                    logger.warning(f"마이크 오디오 스트림 시작 실패: {e}")
                    self._mic_stream = None
            elif self.record_mic and self._loopback_device is None:
                logger.info("루프백 없음: 기본 입력만 사용하여 시스템/마이크 동시 녹음 생략.")
            
            # 적어도 하나의 스트림이 시작되었는지 확인
            if self._system_stream is None and self._mic_stream is None:
                logger.error("오디오 스트림을 시작할 수 없습니다")
                return False

            # recording 플래그를 스트림 시작 직후 설정 (콜백 프레임 손실 방지)
            self.recording = True
            return True
            
        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"오디오 녹음 시작 실패: {e}")
            # 부분적으로 시작된 스트림 정리
            self._cleanup_streams()
            self.recording = False
            return False
    
    def _cleanup_streams(self):
        """오디오 스트림 정리 (내부 헬퍼)"""
        if self._system_stream is not None:
            try:
                self._system_stream.stop()
                self._system_stream.close()
            except Exception:
                pass
            self._system_stream = None
        
        if self._mic_stream is not None:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None
    
    def stop(self) -> Optional[str]:
        """
        오디오 녹음 중지 및 WAV 파일 저장 (시스템 + 마이크 병합)
        
        Returns:
            저장된 WAV 파일 경로 또는 None (실패 시)
        """
        if not self.recording:
            return None
        
        try:
            # 플래그를 먼저 해제하여 콜백이 더 이상 버퍼에 쓰지 않도록 함
            self.recording = False

            # 스트림 중지 (플래그 해제 후이므로 콜백이 실행되어도 안전)
            self._cleanup_streams()
            
            # 녹음된 데이터 확인
            with self._lock:
                has_system = len(self.system_audio_data) > 0
                has_mic = len(self.mic_audio_data) > 0
                
                if not has_system and not has_mic:
                    return None
                
                # 오디오 병합
                if has_system and has_mic:
                    # 두 오디오를 병합
                    merged_audio = self._merge_audio()
                    if merged_audio is None:
                        return None
                    audio_array = merged_audio
                    sample_rate = max(self.system_sample_rate, self.mic_sample_rate)
                elif has_system:
                    audio_array = np.concatenate(self.system_audio_data, axis=0)
                    sample_rate = self.system_sample_rate
                else:  # has_mic
                    audio_array = np.concatenate(self.mic_audio_data, axis=0)
                    sample_rate = self.mic_sample_rate
                
                self.system_audio_data = []
                self.mic_audio_data = []
            
            # 임시 WAV 파일로 저장 (보안: mkstemp 사용)
            fd, self._temp_file = tempfile.mkstemp(suffix='.wav', prefix='giffy_audio_')
            os.close(fd)  # soundfile이 파일을 직접 열기 때문에 fd 닫음
            sf.write(self._temp_file, audio_array, sample_rate)
            
            return self._temp_file
            
        except (IOError, OSError, ValueError) as e:
            logger.error(f"오디오 저장 실패: {e}")
            return None
    
    def _merge_audio(self) -> Optional[np.ndarray]:
        """시스템 오디오와 마이크 오디오 병합"""
        try:
            # 각각의 오디오 배열 생성
            system_array = np.concatenate(self.system_audio_data, axis=0)
            mic_array = np.concatenate(self.mic_audio_data, axis=0)
            
            # 샘플 레이트 통일 (더 높은 레이트로 리샘플링)
            target_rate = max(self.system_sample_rate, self.mic_sample_rate)
            
            if self.system_sample_rate != target_rate:
                # 시스템 오디오 리샘플링
                from scipy import signal
                num_samples = int(len(system_array) * target_rate / self.system_sample_rate)
                system_array = signal.resample(system_array, num_samples, axis=0)
            
            if self.mic_sample_rate != target_rate:
                # 마이크 오디오 리샘플링
                from scipy import signal
                num_samples = int(len(mic_array) * target_rate / self.mic_sample_rate)
                mic_array = signal.resample(mic_array, num_samples, axis=0)
            
            # 길이 맞추기 (짧은 쪽에 제로 패딩)
            max_len = max(len(system_array), len(mic_array))
            if len(system_array) < max_len:
                padding = np.zeros((max_len - len(system_array), system_array.shape[1]))
                system_array = np.vstack([system_array, padding])
            if len(mic_array) < max_len:
                padding = np.zeros((max_len - len(mic_array), mic_array.shape[1]))
                mic_array = np.vstack([mic_array, padding])
            
            # 채널 수 맞추기
            if system_array.shape[1] != mic_array.shape[1]:
                if system_array.shape[1] == 1:
                    system_array = np.repeat(system_array, mic_array.shape[1], axis=1)
                elif mic_array.shape[1] == 1:
                    mic_array = np.repeat(mic_array, system_array.shape[1], axis=1)
            
            # 두 오디오 합산 (볼륨 조절 가능)
            merged = system_array + mic_array
            
            # 클리핑 방지 (정규화)
            max_val = np.abs(merged).max()
            if max_val > 1.0:
                merged = merged / max_val
            
            return merged
            
        except ImportError:
            # scipy가 없으면 FFmpeg로 병합
            return self._merge_audio_with_ffmpeg()
        except (ValueError, RuntimeError) as e:
            logger.error(f"오디오 병합 실패: {e}")
            return None
    
    def _merge_audio_with_ffmpeg(self) -> Optional[np.ndarray]:
        """FFmpeg를 사용한 오디오 병합 (scipy 없을 때)"""
        system_file = None
        mic_file = None
        merged_file = None
        
        try:
            # 각각을 임시 파일로 저장 (보안: mkstemp 사용)
            fd1, system_file = tempfile.mkstemp(suffix='.wav', prefix='giffy_system_')
            fd2, mic_file = tempfile.mkstemp(suffix='.wav', prefix='giffy_mic_')
            fd3, merged_file = tempfile.mkstemp(suffix='.wav', prefix='giffy_merged_')
            os.close(fd1)
            os.close(fd2)
            os.close(fd3)
            
            system_array = np.concatenate(self.system_audio_data, axis=0)
            mic_array = np.concatenate(self.mic_audio_data, axis=0)
            
            sf.write(system_file, system_array, self.system_sample_rate)
            sf.write(mic_file, mic_array, self.mic_sample_rate)
            
            # FFmpeg로 병합
            ffmpeg_path = os.environ.get('FFMPEG_PATH', 'ffmpeg')
            cmd = [
                ffmpeg_path,
                '-y',
                '-i', system_file,
                '-i', mic_file,
                '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=longest',
                '-ar', '44100',
                merged_file
            ]
            
            result = run_subprocess_silent(cmd)
            
            if result.returncode == 0 and os.path.exists(merged_file):
                # 병합된 파일 읽기
                merged_array, sr = sf.read(merged_file)
                return merged_array
            else:
                # FFmpeg 실패 시 시스템 오디오만 반환
                return np.concatenate(self.system_audio_data, axis=0)
                
        except (subprocess.SubprocessError, IOError, OSError) as e:
            logger.warning(f"FFmpeg 오디오 병합 실패: {e}")
            # 실패 시 시스템 오디오만 반환
            return np.concatenate(self.system_audio_data, axis=0) if self.system_audio_data else None
        finally:
            # 임시 파일 항상 정리
            for f in [system_file, mic_file, merged_file]:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass
    
    def cleanup(self):
        """임시 파일 정리"""
        if self._temp_file and os.path.exists(self._temp_file):
            try:
                os.remove(self._temp_file)
            except Exception:
                pass
            self._temp_file = None
    
    def is_recording(self) -> bool:
        """녹음 중 여부"""
        return self.recording


def is_audio_available() -> bool:
    """오디오 녹음 기능 사용 가능 여부"""
    return HAS_AUDIO
