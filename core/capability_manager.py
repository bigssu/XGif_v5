"""
Capability Manager
시스템 능력 감지 및 최적 파이프라인 자동 선택
"""

import json
import os
import time
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
from pathlib import Path

from .gpu_utils import detect_gpu, get_detailed_gpu_info, is_gpu_available

# 로깅 설정
logger = logging.getLogger(__name__)
from .capture_backend import (
    get_available_backends, is_dxcam_available,
    create_capture_backend, test_capture_backend
)


@dataclass
class Pipeline:
    """파이프라인 설정"""
    name: str
    capture_backend: str  # "dxcam" or "gdi"
    encoder: str  # "h264_nvenc", "hevc_nvenc", "h264_qsv", etc.
    codec: str  # "h264" or "h265"
    score: int  # 성능 점수 (높을수록 좋음)
    description: str


@dataclass
class SystemCapabilities:
    """시스템 능력 정보"""
    # GPU 정보
    has_nvidia_gpu: bool = False
    gpu_name: Optional[str] = None
    gpu_memory_mb: int = 0
    driver_version: Optional[str] = None
    
    # 캡처 백엔드
    has_dxcam: bool = False
    dxcam_working: bool = False
    
    # 인코더
    available_encoders: Dict[str, List[str]] = None
    best_h264_encoder: Optional[str] = None
    best_h265_encoder: Optional[str] = None
    
    # 최적 파이프라인
    optimal_pipeline: Optional[Pipeline] = None
    
    # 감지 시간
    detected_at: float = 0.0
    
    def __post_init__(self):
        if self.available_encoders is None:
            self.available_encoders = {'h264': [], 'h265': []}


class CapabilityManager:
    """시스템 Capability 감지 및 최적 파이프라인 선택"""
    
    # 캐시 파일 경로
    CACHE_FILENAME = "capability_cache.json"
    CACHE_MAX_AGE_SECONDS = 86400  # 24시간
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Args:
            cache_dir: 캐시 파일 저장 디렉토리 (None이면 %APPDATA%/XGif)
        """
        if cache_dir:
            self._cache_dir = Path(cache_dir)
        else:
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            self._cache_dir = Path(appdata) / 'XGif'
        
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path = self._cache_dir / self.CACHE_FILENAME
        
        self._capabilities: Optional[SystemCapabilities] = None
    
    def detect_capabilities(self, force_refresh: bool = False) -> SystemCapabilities:
        """시스템 능력 감지
        
        Args:
            force_refresh: True면 캐시 무시하고 재감지
            
        Returns:
            SystemCapabilities: 감지된 시스템 능력
        """
        # 캐시 확인
        if not force_refresh and self._capabilities is not None:
            return self._capabilities
        
        # 캐시 파일에서 로드 시도
        if not force_refresh:
            cached = self._load_cache()
            if cached is not None:
                self._capabilities = cached
                return cached
        
        logger.info("시스템 능력 감지 시작...")
        start_time = time.time()
        
        caps = SystemCapabilities()
        caps.detected_at = time.time()
        
        # 1. GPU 정보 감지
        self._detect_gpu(caps)
        
        # 2. 캡처 백엔드 감지
        self._detect_capture_backends(caps)
        
        # 3. 인코더 감지
        self._detect_encoders(caps)
        
        # 4. 최적 파이프라인 선택
        caps.optimal_pipeline = self._select_optimal_pipeline(caps)
        
        elapsed = time.time() - start_time
        logger.info(f"감지 완료 ({elapsed:.2f}초)")
        logger.info(f"최적 파이프라인: {caps.optimal_pipeline.name if caps.optimal_pipeline else 'N/A'}")
        
        # 캐시 저장
        self._save_cache(caps)
        self._capabilities = caps
        
        return caps
    
    def _detect_gpu(self, caps: SystemCapabilities):
        """GPU 정보 감지 (CuPy 초기화 스킵 — 하드웨어 정보만)"""
        gpu_info = detect_gpu(skip_cupy=True)
        
        caps.has_nvidia_gpu = gpu_info.has_cuda
        caps.gpu_name = gpu_info.gpu_name
        caps.gpu_memory_mb = gpu_info.gpu_memory_mb
        caps.driver_version = gpu_info.driver_version
        
        if caps.has_nvidia_gpu:
            logger.info(f"GPU: {caps.gpu_name} ({caps.gpu_memory_mb}MB)")
        else:
            logger.info("NVIDIA GPU 없음")
    
    def _detect_capture_backends(self, caps: SystemCapabilities):
        """캡처 백엔드 감지"""
        caps.has_dxcam = is_dxcam_available()
        
        # dxcam 실제 작동 테스트
        if caps.has_dxcam:
            try:
                backend = create_capture_backend("dxcam")
                # 작은 영역으로 테스트
                caps.dxcam_working = test_capture_backend(backend, (0, 0, 100, 100))
            except (RuntimeError, OSError) as e:
                logger.warning(f"dxcam 테스트 실패: {e}")
                caps.dxcam_working = False
        
        logger.info(f"캡처 백엔드: dxcam={caps.dxcam_working}, gdi=available")
    
    def _detect_encoders(self, caps: SystemCapabilities):
        """인코더 감지"""
        try:
            from .gif_encoder import GifEncoder
            encoder = GifEncoder()
            available = encoder.detect_available_encoders()
            
            caps.available_encoders = {
                'h264': available.get('h264', ['libx264']),
                'h265': available.get('h265', ['libx265']),
            }
            caps.best_h264_encoder = available.get('best_h264', 'libx264')
            caps.best_h265_encoder = available.get('best_h265', 'libx265')
            
            logger.info(f"H.264 인코더: {caps.available_encoders['h264']}")
            logger.info(f"H.265 인코더: {caps.available_encoders['h265']}")
            
        except (ImportError, RuntimeError, OSError) as e:
            logger.warning(f"인코더 감지 실패: {e}")
            caps.available_encoders = {'h264': ['libx264'], 'h265': ['libx265']}
            caps.best_h264_encoder = 'libx264'
            caps.best_h265_encoder = 'libx265'
    
    def _select_optimal_pipeline(self, caps: SystemCapabilities) -> Pipeline:
        """최적 파이프라인 선택"""
        pipelines = []
        
        # 캡처 백엔드 결정
        capture_backend = "dxcam" if caps.dxcam_working else "gdi"
        capture_score = 20 if capture_backend == "dxcam" else 15
        
        # H.265 파이프라인 (호환성 문제로 우선순위 낮음 — Windows 기본 코덱에 HEVC 미포함)
        if caps.best_h265_encoder:
            encoder = caps.best_h265_encoder
            if 'nvenc' in encoder:
                score = capture_score + 40
                name = "Pipeline: DXGI + NVENC H.265" if capture_backend == "dxcam" else "Pipeline: GDI + NVENC H.265"
            elif 'qsv' in encoder:
                score = capture_score + 30
                name = f"Pipeline: {capture_backend.upper()} + QSV H.265"
            elif 'amf' in encoder:
                score = capture_score + 30
                name = f"Pipeline: {capture_backend.upper()} + AMF H.265"
            else:
                score = capture_score + 10
                name = f"Pipeline: {capture_backend.upper()} + x265 (CPU)"
            
            pipelines.append(Pipeline(
                name=name,
                capture_backend=capture_backend,
                encoder=encoder,
                codec='h265',
                score=score,
                description=f"H.265 코덱, {encoder} 인코더"
            ))
        
        # H.264 파이프라인 (우선순위 높음 — Windows 기본 코덱으로 재생 가능)
        if caps.best_h264_encoder:
            encoder = caps.best_h264_encoder
            if 'nvenc' in encoder:
                score = capture_score + 50
                name = f"Pipeline A: {capture_backend.upper()} + NVENC H.264" if capture_backend == "dxcam" else f"Pipeline B: {capture_backend.upper()} + NVENC H.264"
            elif 'qsv' in encoder:
                score = capture_score + 40
                name = f"Pipeline: {capture_backend.upper()} + QSV H.264"
            elif 'amf' in encoder:
                score = capture_score + 40
                name = f"Pipeline: {capture_backend.upper()} + AMF H.264"
            else:
                score = capture_score + 15
                name = f"Pipeline: {capture_backend.upper()} + x264 (CPU)"
            
            pipelines.append(Pipeline(
                name=name,
                capture_backend=capture_backend,
                encoder=encoder,
                codec='h264',
                score=score,
                description=f"H.264 코덱, {encoder} 인코더"
            ))
        
        # 점수순 정렬
        pipelines.sort(key=lambda p: p.score, reverse=True)
        
        # 최적 파이프라인 반환
        if pipelines:
            return pipelines[0]
        
        # 폴백
        return Pipeline(
            name="Pipeline: GDI + x264 (Fallback)",
            capture_backend="gdi",
            encoder="libx264",
            codec="h264",
            score=15,
            description="기본 CPU 인코딩"
        )
    
    def get_optimal_pipeline(self) -> Pipeline:
        """최적 파이프라인 반환"""
        if self._capabilities is None:
            self.detect_capabilities()
        
        # optimal_pipeline이 None이면 기본 파이프라인 생성
        if self._capabilities.optimal_pipeline is None:
            self._capabilities.optimal_pipeline = Pipeline(
                name="Pipeline: GDI + x264 (Fallback)",
                capture_backend="gdi",
                encoder="libx264",
                codec="h264",
                score=15,
                description="기본 CPU 인코딩"
            )
        
        return self._capabilities.optimal_pipeline
    
    def get_capabilities(self) -> SystemCapabilities:
        """현재 Capabilities 반환"""
        if self._capabilities is None:
            self.detect_capabilities()
        return self._capabilities
    
    def get_capabilities_summary(self) -> str:
        """Capabilities 요약 문자열 반환"""
        caps = self.get_capabilities()
        
        lines = []
        
        # GPU
        if caps.has_nvidia_gpu:
            lines.append(f"GPU: {caps.gpu_name} ({caps.gpu_memory_mb}MB)")
        else:
            lines.append("GPU: 없음 (CPU 모드)")
        
        # 캡처 백엔드
        backend = "dxcam" if caps.dxcam_working else "gdi"
        lines.append(f"캡처: {backend}")
        
        # 인코더
        lines.append(f"H.264: {caps.best_h264_encoder or 'libx264'}")
        lines.append(f"H.265: {caps.best_h265_encoder or 'libx265'}")
        
        # 파이프라인
        pipeline = self.get_optimal_pipeline()  # None 안전 메서드 사용
        lines.append(f"파이프라인: {pipeline.name}")
        
        return "\n".join(lines)
    
    def _load_cache(self) -> Optional[SystemCapabilities]:
        """캐시에서 로드"""
        try:
            if not self._cache_path.exists():
                return None
            
            # 파일 크기 검증 (너무 크면 손상된 것으로 간주)
            file_size = self._cache_path.stat().st_size
            if file_size > 1024 * 1024:  # 1MB 초과
                logger.warning(f"Cache file too large: {file_size} bytes")
                return None
            
            if file_size == 0:
                logger.warning("Cache file is empty")
                return None
            
            with open(self._cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 앱 버전 변경 시 캐시 무효화
            from .version import APP_VERSION
            if data.get('app_version') != APP_VERSION:
                logger.info("캐시 무효화: 앱 버전 변경 (%s → %s)", data.get('app_version'), APP_VERSION)
                return None

            # 캐시 만료 확인
            detected_at = data.get('detected_at', 0)
            if time.time() - detected_at > self.CACHE_MAX_AGE_SECONDS:
                logger.debug("Cache expired")
                return None
            
            # SystemCapabilities 복원
            caps = SystemCapabilities(
                has_nvidia_gpu=data.get('has_nvidia_gpu', False),
                gpu_name=data.get('gpu_name'),
                gpu_memory_mb=data.get('gpu_memory_mb', 0),
                driver_version=data.get('driver_version'),
                has_dxcam=data.get('has_dxcam', False),
                dxcam_working=data.get('dxcam_working', False),
                available_encoders=data.get('available_encoders', {'h264': [], 'h265': []}),
                best_h264_encoder=data.get('best_h264_encoder'),
                best_h265_encoder=data.get('best_h265_encoder'),
                detected_at=detected_at,
            )
            
            # 파이프라인 복원 (필수 필드 검증)
            pipeline_data = data.get('optimal_pipeline')
            required_fields = ['name', 'capture_backend', 'encoder', 'codec', 'score', 'description']
            if pipeline_data and all(k in pipeline_data for k in required_fields):
                caps.optimal_pipeline = Pipeline(**pipeline_data)
            else:
                caps.optimal_pipeline = None
            
            logger.info("캐시에서 로드됨")
            return caps
            
        except (IOError, json.JSONDecodeError, KeyError) as e:
            logger.warning(f"캐시 로드 실패: {e}")
            return None
    
    def _save_cache(self, caps: SystemCapabilities):
        """캐시에 저장"""
        try:
            # 디렉토리 존재 확인
            if not self._cache_dir.exists():
                self._cache_dir.mkdir(parents=True, exist_ok=True)
            
            from .version import APP_VERSION
            data = {
                'app_version': APP_VERSION,
                'has_nvidia_gpu': caps.has_nvidia_gpu,
                'gpu_name': caps.gpu_name,
                'gpu_memory_mb': caps.gpu_memory_mb,
                'driver_version': caps.driver_version,
                'has_dxcam': caps.has_dxcam,
                'dxcam_working': caps.dxcam_working,
                'available_encoders': caps.available_encoders,
                'best_h264_encoder': caps.best_h264_encoder,
                'best_h265_encoder': caps.best_h265_encoder,
                'detected_at': caps.detected_at,
            }
            
            if caps.optimal_pipeline:
                data['optimal_pipeline'] = asdict(caps.optimal_pipeline)
            
            with open(self._cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"캐시 저장됨: {self._cache_path}")
            
        except (IOError, OSError) as e:
            logger.warning(f"캐시 저장 실패: {e}")
    
    def clear_cache(self):
        """캐시 삭제"""
        try:
            if self._cache_path.exists():
                self._cache_path.unlink()
            self._capabilities = None
            logger.info("캐시 삭제됨")
        except OSError as e:
            logger.warning(f"캐시 삭제 실패: {e}")


# 싱글톤 인스턴스
_capability_manager: Optional[CapabilityManager] = None


def get_capability_manager() -> CapabilityManager:
    """CapabilityManager 싱글톤 인스턴스 반환"""
    global _capability_manager
    if _capability_manager is None:
        _capability_manager = CapabilityManager()
    return _capability_manager
