"""
I18N (Internationalization) Manager - 통합 번역 모듈
메인 앱 및 GIF 에디터 모두 지원
Supports Korean (default) and English
"""

import os
from typing import Dict, Any, Optional, Callable, List


class TranslationManager:
    """Translation manager with callback to notify UI of language changes"""
    
    _instance = None
    _callbacks: List[Callable[[str], None]] = []
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = TranslationManager()
        return cls._instance
        
    def __init__(self):
        self._current_lang = 'ko'
        self._initialized = True
        self._callbacks = []
        
        # ═══════════════════════════════════════════════════════════════
        # 메인 앱 번역 (화면 녹화)
        # ═══════════════════════════════════════════════════════════════
        self._main_translations_ko = {
            # Settings Dialog
            'settings': '설정',
            'language': '언어',
            'language_ko': '한국어',
            'language_en': 'English',
            'language_tooltip': '애플리케이션 언어를 선택합니다',
            'audio': '오디오',
            'mic_recording': '마이크 오디오 녹음',
            'mic_recording_tooltip': 'MP4 녹화 시 마이크 오디오를 포함합니다',
            'overlay': '오버레이',
            'webcam_overlay': '웹캠 오버레이',
            'webcam_overlay_tooltip': '녹화 화면에 웹캠 영상을 오버레이합니다',
            'watermark': '워터마크',
            'watermark_tooltip': '녹화 영상에 워터마크를 추가합니다',
            'interaction': '인터랙션 표시',
            'click_highlight': '마우스 클릭 하이라이트',
            'click_highlight_tooltip': '마우스 클릭 시 시각적 효과를 표시합니다',
            'keyboard_display': '키보드 입력 표시',
            'keyboard_display_tooltip': '키보드 입력을 화면에 텍스트로 표시합니다',
            'preview': '미리보기',
            'realtime_preview': '실시간 미리보기',
            'realtime_preview_tooltip': '녹화 전/중 실시간 프레임 미리보기를 표시합니다',
            'memory_management': '메모리 관리',
            'max_memory': '최대 사용 메모리:',
            'max_memory_tooltip': '녹화 중 사용할 최대 메모리를 설정합니다.\n설정치에 도달하면 녹화가 자동으로 중지됩니다.',
            'gpu_encoder': 'GPU 및 인코더',
            'capture_backend': '캡처 백엔드:',
            'capture_backend_tooltip': "화면 캡처 방식 선택\\nAuto: HDR ON → GDI (색상 정확), HDR OFF → dxcam (고성능)\\ndxcam: DXGI 고성능 캡처\\nGDI (색상 정확): Windows GDI - HDR 환경에서 권장",
            'encoder': '인코더:',
            'encoder_tooltip': "비디오 인코더 선택\\nAuto: 자동 (최적 선택)\\nNVENC: NVIDIA GPU\\nQSV: Intel GPU\\nAMF: AMD GPU\\nCPU: 소프트웨어",
            'codec': '코덱:',
            'codec_tooltip': "비디오 코덱 선택\\nH.264: 호환성 좋음\\nH.265: 압축률 높음 (파일 크기 작음)",
            'reset_defaults': '기본값으로 복원',
            'reset_tooltip': '모든 설정을 기본값으로 되돌립니다',
            'reset_confirm_title': '기본값 복원',
            'reset_confirm_msg': '모든 설정을 기본값으로 복원하시겠습니까?',
            'settings_saved': '설정이 저장되었습니다',
            'settings_reset': '기본값으로 복원되었습니다',
            'save_failed': '설정 저장 실패',
            'already_running': 'XGif가 이미 실행 중입니다.\n기존 인스턴스를 사용하세요.',
            'already_running_ask_title': 'XGif가 이미 실행 중입니다',
            'already_running_ask_msg': 'XGif가 이미 실행 중입니다. 기존 앱을 종료하고 새로 시작하시겠습니까?',
            'already_running_restart': '기존 종료 후 새로 시작',
            'already_running_cancel': '취소',
            'already_running_quit_failed': '기존 앱을 종료할 수 없습니다. 나중에 다시 시도하세요.',
            'warning': '경고',
            'error': '오류',
            'info': '정보',
            'confirm': '확인',
            'cancel': '취소',
            'ok': '확인',
            'file': '파일',
            
            # FFmpeg
            'ffmpeg_install_title': 'FFmpeg 설치',
            'ffmpeg_install_msg': '고화질 GIF 생성을 위해 FFmpeg가 필요합니다.\n\n자동으로 다운로드하여 설치하시겠습니까?\n(약 80MB, 1-2분 소요)',
            'ffmpeg_downloading': 'FFmpeg 다운로드 중...',
            'install_complete': '설치 완료',
            'ffmpeg_install_success': 'FFmpeg가 성공적으로 설치되었습니다.',
            'install_failed': '설치 실패',
            'ffmpeg_install_failed': 'FFmpeg 설치에 실패했습니다: {}',

            # dxcam
            'dxcam_install_title': 'dxcam 설치',
            'dxcam_install_msg': 'dxcam이 설치되어 있지 않습니다.\n\nDXGI 고성능 캡처를 사용하려면 dxcam 패키지가 필요합니다.\n지금 설치하시겠습니까? (인터넷 필요)',
            'dxcam_installing': 'dxcam 설치 중... 잠시 기다려주세요.',
            'dxcam_install_success': 'dxcam이 설치되었습니다. 적용하려면 앱을 재시작하세요.',
            'dxcam_install_failed': 'dxcam 설치 실패: {}',

            # 의존성 다이얼로그
            'dep_dialog_title': '의존성 설치',
            'dep_install_btn': '설치',
            'dep_download_btn': '다운로드',
            'dep_rescan_btn': '재검사',
            'dep_skip_btn': '건너뛰기',
            'dep_close_btn': '닫기',
            'dep_dont_ask_again': '다시 묻지 않기',
            'dep_state_installed': '설치됨',
            'dep_state_missing': '미설치',
            'dep_state_version_low': '버전 낮음 ({})',
            'dep_state_error': '오류',
            'dep_ffmpeg_desc': 'MP4 녹화 및 고화질 GIF 생성에 필수',
            'dep_ffmpeg_required_for_record': 'MP4 녹화에 FFmpeg가 필요합니다.\n자동으로 다운로드하여 설치하시겠습니까?',
            'dep_use_gif_instead': 'GIF로 녹화',
            'dep_ffmpeg_install_guide': '1. 아래 "다운로드" 버튼으로 자동 설치\n2. 또는 ffmpeg.org에서 직접 다운로드',
            'dep_ffmpeg_manual_url': 'https://ffmpeg.org/download.html',
            'dep_cupy_desc': 'GPU 가속에 필요 (CuPy 12.0 이상)\n미설치 시 CPU 모드로 동작',
            'dep_use_cpu_instead': 'CPU 모드 사용',
            'dep_cupy_install_guide': '터미널에서 다음 명령어를 실행하세요:\n\npip install cupy-cuda12x\n\nCUDA 버전에 맞는 패키지를 설치해야 합니다.',
            'dep_cupy_installed_ok': 'CuPy가 정상적으로 감지되었습니다!',
            'dep_cupy_still_missing': 'CuPy를 찾을 수 없습니다.\n설치 후 다시 시도하세요.',
            'dep_dxcam_desc': 'GPU 가속 캡처 (DXGI)\nHDR 환경에서 색상이 부정확할 수 있음',
            'dep_use_gdi_instead': 'GDI (색상 정확) 사용',
            'dep_startup_title': '환경 진단',
            'dep_startup_desc': '앱을 최대한 활용하기 위해 아래 항목을 확인하세요.',
            'dep_rescan_title': '재검사',
            'dep_reset_skip_flags': '의존성 확인 초기화',
            'dep_reset_skip_flags_tooltip': '건너뛴 의존성 확인을 모두 초기화합니다',
            'dep_skip_flags_reset': '의존성 확인이 초기화되었습니다',
            'dep_ffmpeg_download_failed': 'FFmpeg 다운로드에 실패했습니다.\n브라우저에서 직접 다운로드하시겠습니까?',

            # Hardware / Status
            'webcam_unavailable': '웹캠을 사용할 수 없습니다.\nOpenCV가 설치되어 있는지 확인하세요.',
            'keyboard_unavailable': '키보드 입력 감지를 사용할 수 없습니다.\npynput 라이브러리가 설치되어 있는지 확인하세요.',
            'recorder_not_init': '녹화기가 초기화되지 않았습니다.',
            'region_not_set': '녹화 영역이 설정되지 않았습니다.\n캡처 영역을 먼저 선택해주세요.',
            
            # Control Bar
            'output_format_tooltip': '출력 파일 형식',
            'fps': 'FPS',
            'fps_label_tooltip': '초당 프레임 수 (Frames Per Second)',
            'fps_tooltip': '초당 프레임 수',
            'resolution_tooltip': '캡처 영역 해상도',
            'resolution_tooltip_custom': '해상도 선택 또는 직접 입력 (예: 1920x1080, 50~3840)',
            'quality_tooltip': '출력 품질 (Hi=고품질, Lo=저용량)',
            'cursor_tooltip': '마우스 커서 포함',
            'click_highlight_icon_tooltip': '클릭 하이라이트 표시',
            'gpu_status_tooltip': 'GPU 가속 상태',
            'rec_tooltip': '녹화 시작/종료 (F9)',
            'pause_tooltip': '녹화 일시정지/재개 (F9)',
            'stop_tooltip': '녹화 중지 (F10)',
            'settings_tooltip': '설정',
            'hdr_label_tooltip': 'HDR 모니터 사용 중 - Windows 색상 관리가 자동으로 적용됩니다',
            
            # Main Window
            'recording': '녹화 중...',
            'paused': '일시정지 - 캡처 영역을 이동할 수 있습니다 (크기 변경 불가)',
            'no_frames': '녹화된 프레임이 없습니다.',
            'save_complete': '✓ 저장 완료!',
            'encoding': '{} 인코딩 중...',
            'optimized': '최적화 완료: {}',
            'ready': '준비 - 캡처 영역을 조정하세요',
            'start_failed': '녹화 시작 실패: {}',
            'mem_limit_reached': '메모리 한계 도달',
            'mem_limit_msg': '설정된 메모리 한계({}MB)에 도달하여 녹화를 자동으로 중지합니다.',
            'audio_buffer_limit_reached': '오디오 버퍼 한계에 도달하여 녹화를 자동으로 중지합니다.',
            'low_fps_warning_title': '캡처 성능 경고',
            'low_fps_warning_msg': '실제 캡처 FPS({actual_fps:.1f})가 목표 FPS({target_fps})보다 낮습니다.\n\n권장 사항:\n• 해상도를 낮추기\n• 품질을 낮추기\n• 오버레이 기능 비활성화\n• 다른 프로그램 종료',
            'mem_warning': '⚠ 메모리 사용량이 한계치에 가깝습니다 ({} / {} MB)',
            'sys_mem_low_title': '시스템 메모리 부족',
            'sys_mem_low_msg': '시스템 가용 메모리가 매우 부족합니다 ({}MB).\n데이터 손실 방지를 위해 녹화를 자동으로 중지합니다.',
            'quit_confirm_title': '확인',
            'quit_confirm_msg': '녹화 중입니다. 정말 종료하시겠습니까?',
            'save_dir_mem': '저장 디렉토리 기억',
            'save_gif': 'GIF 저장',
            'save_mp4': 'MP4 저장',
            'saved_to': '저장됨: {}',
            'saved_to_path': '파일이 다음 경로에 저장되었습니다:\n{}',
            'encoding_finished_msg': '저장됨: {}{}',
            'encoding_failed': '인코딩 실패',
            'encoding_percent': '{} 인코딩 중... ({}%)',
            'recording_error': '녹화 오류: {}',
            'capture_no_frames_warning': '캡처가 되지 않습니다. 백엔드를 확인하세요.',
            'system_memory_low': '시스템 가용 메모리가 매우 부족합니다 ({}MB).',
            'folder_open_failed': '파일이 저장되었습니다:\n{}',
            
            # Backend options
            'high': '상',
            'medium': '중',
            'low': '하',
            'auto': '자동',
            'cpu': 'CPU',
            
            # Recording complete dialog (Integration)
            'recording_complete': '녹화 완료',
            'recording_complete_msg': '{}개 프레임이 녹화되었습니다.\n어떻게 하시겠습니까?',
            'save_now': '💾 저장',
            'edit_now': '✏️ 편집',
            'discard': '🗑️ 삭제',
            'opening_editor': '편집기 열기...',
            'editor_opened': '편집기가 열렸습니다. 녹화된 프레임을 편집하세요.',
            'frames_loaded': '{}개 프레임이 편집기에 로드되었습니다.',
        }
        
        self._main_translations_en = {
            # Settings Dialog
            'settings': 'Settings',
            'language': 'Language',
            'language_ko': 'Korean',
            'language_en': 'English',
            'language_tooltip': 'Select application language',
            'audio': 'Audio',
            'mic_recording': 'Record Microphone Audio',
            'mic_recording_tooltip': 'Includes microphone audio in MP4 recordings',
            'overlay': 'Overlay',
            'webcam_overlay': 'Webcam Overlay',
            'webcam_overlay_tooltip': 'Overlays webcam video on the recording screen',
            'watermark': 'Watermark',
            'watermark_tooltip': 'Adds a watermark to the recorded video',
            'interaction': 'Interaction Display',
            'click_highlight': 'Mouse Click Highlight',
            'click_highlight_tooltip': 'Displays visual effects on mouse clicks',
            'keyboard_display': 'Keyboard Input Display',
            'keyboard_display_tooltip': 'Displays keyboard input as text on screen',
            'preview': 'Preview',
            'realtime_preview': 'Real-time Preview',
            'realtime_preview_tooltip': 'Displays real-time frame preview before/during recording',
            'memory_management': 'Memory Management',
            'max_memory': 'Max Memory Usage:',
            'max_memory_tooltip': 'Sets the maximum memory to use during recording.\nRecording stops automatically when reached.',
            'gpu_encoder': 'GPU & Encoder',
            'capture_backend': 'Capture Backend:',
            'capture_backend_tooltip': "Choose capture method\\nAuto: HDR ON → GDI (color accurate), HDR OFF → dxcam (fast)\\ndxcam: DXGI high-performance\\nGDI (color accurate): Windows GDI - recommended for HDR",
            'encoder': 'Encoder:',
            'encoder_tooltip': "Choose video encoder\\nAuto: Automatic (optimal)\\nNVENC: NVIDIA GPU\\nQSV: Intel GPU\\nAMF: AMD GPU\\nCPU: Software",
            'codec': 'Codec:',
            'codec_tooltip': "Choose video codec\\nH.264: Good compatibility\\nH.265: High compression (smaller size)",
            'reset_defaults': 'Reset to Defaults',
            'reset_tooltip': 'Resets all settings to their default values',
            'reset_confirm_title': 'Reset Defaults',
            'reset_confirm_msg': 'Are you sure you want to reset all settings to defaults?',
            'settings_saved': 'Settings saved successfully',
            'settings_reset': 'Settings reset to defaults',
            'save_failed': 'Failed to save settings',
            'already_running': 'XGif is already running.\nPlease use the existing instance.',
            'already_running_ask_title': 'XGif is already running',
            'already_running_ask_msg': 'XGif is already running. Do you want to quit the existing app and start a new one?',
            'already_running_restart': 'Quit existing and restart',
            'already_running_cancel': 'Cancel',
            'already_running_quit_failed': 'Could not quit the existing app. Please try again later.',
            'warning': 'Warning',
            'error': 'Error',
            'info': 'Information',
            'confirm': 'Confirm',
            'cancel': 'Cancel',
            'ok': 'OK',
            'file': 'File',
            
            # FFmpeg
            'ffmpeg_install_title': 'FFmpeg Installation',
            'ffmpeg_install_msg': 'FFmpeg is required for high-quality GIF creation.\n\nDo you want to download and install it automatically?\n(Approx. 80MB, takes 1-2 mins)',
            'ffmpeg_downloading': 'Downloading FFmpeg...',
            'install_complete': 'Installation Complete',
            'ffmpeg_install_success': 'FFmpeg has been installed successfully.',
            'install_failed': 'Installation Failed',
            'ffmpeg_install_failed': 'Failed to install FFmpeg: {}',

            # dxcam
            'dxcam_install_title': 'Install dxcam',
            'dxcam_install_msg': 'dxcam is not installed.\n\nThe dxcam package is required for DXGI high-performance capture.\nWould you like to install it now? (Internet required)',
            'dxcam_installing': 'Installing dxcam... Please wait.',
            'dxcam_install_success': 'dxcam has been installed. Restart the app to apply.',
            'dxcam_install_failed': 'Failed to install dxcam: {}',

            # Dependency dialogs
            'dep_dialog_title': 'Dependency Installation',
            'dep_install_btn': 'Install',
            'dep_download_btn': 'Download',
            'dep_rescan_btn': 'Rescan',
            'dep_skip_btn': 'Skip',
            'dep_close_btn': 'Close',
            'dep_dont_ask_again': "Don't ask again",
            'dep_state_installed': 'Installed',
            'dep_state_missing': 'Not installed',
            'dep_state_version_low': 'Version too low ({})',
            'dep_state_error': 'Error',
            'dep_ffmpeg_desc': 'Required for MP4 recording and high-quality GIF creation',
            'dep_ffmpeg_required_for_record': 'FFmpeg is required for MP4 recording.\nWould you like to download and install it automatically?',
            'dep_use_gif_instead': 'Record as GIF',
            'dep_ffmpeg_install_guide': '1. Click "Download" below for automatic installation\n2. Or download manually from ffmpeg.org',
            'dep_ffmpeg_manual_url': 'https://ffmpeg.org/download.html',
            'dep_cupy_desc': 'Required for GPU acceleration (CuPy 12.0+)\nFalls back to CPU mode if not installed',
            'dep_use_cpu_instead': 'Use CPU mode',
            'dep_cupy_install_guide': 'Run the following command in terminal:\n\npip install cupy-cuda12x\n\nMake sure to install the package matching your CUDA version.',
            'dep_cupy_installed_ok': 'CuPy was detected successfully!',
            'dep_cupy_still_missing': 'CuPy was not found.\nPlease try again after installation.',
            'dep_dxcam_desc': 'GPU-accelerated capture (DXGI)\nColors may be inaccurate in HDR environments',
            'dep_use_gdi_instead': 'Use GDI (color accurate)',
            'dep_startup_title': 'Environment Check',
            'dep_startup_desc': 'Check the following items to get the most out of the app.',
            'dep_rescan_title': 'Rescan',
            'dep_reset_skip_flags': 'Reset Dependency Checks',
            'dep_reset_skip_flags_tooltip': 'Resets all skipped dependency checks',
            'dep_skip_flags_reset': 'Dependency checks have been reset',
            'dep_ffmpeg_download_failed': 'FFmpeg download failed.\nWould you like to download it manually in the browser?',

            # Hardware / Status
            'webcam_unavailable': 'Webcam is unavailable.\nPlease check if OpenCV is installed.',
            'keyboard_unavailable': 'Keyboard input detection is unavailable.\nPlease check if pynput is installed.',
            'recorder_not_init': 'Recorder is not initialized.',
            'region_not_set': 'Recording region is not set.\nPlease select a capture region first.',
            
            # Control Bar
            'output_format_tooltip': 'Output file format',
            'fps': 'FPS',
            'fps_label_tooltip': 'Frames Per Second',
            'fps_tooltip': 'Frames per second',
            'resolution_tooltip': 'Capture region resolution',
            'resolution_tooltip_custom': 'Select or enter resolution (e.g., 1920x1080, 50~3840)',
            'quality_tooltip': 'Output quality (Hi=High, Lo=Small size)',
            'cursor_tooltip': 'Include mouse cursor',
            'click_highlight_icon_tooltip': 'Show click highlights',
            'gpu_status_tooltip': 'GPU acceleration status',
            'rec_tooltip': 'Start/Stop Recording (F9)',
            'pause_tooltip': 'Pause/Resume Recording (F9)',
            'stop_tooltip': 'Stop Recording (F10)',
            'settings_tooltip': 'Settings',
            'hdr_label_tooltip': 'HDR monitor active - Windows color management automatically applied',
            
            # Main Window
            'recording': 'Recording...',
            'paused': 'Paused - Capture area can be moved (Resize disabled)',
            'no_frames': 'No frames recorded.',
            'save_complete': '✓ Saved Successfully!',
            'encoding': 'Encoding {}...',
            'optimized': 'Optimized: {}',
            'ready': 'Ready - Adjust the capture area',
            'start_failed': 'Failed to start recording: {}',
            'mem_limit_reached': 'Memory Limit Reached',
            'mem_limit_msg': 'Recording automatically stopped as set memory limit ({}MB) was reached.',
            'audio_buffer_limit_reached': 'Recording stopped automatically because the audio buffer limit was reached.',
            'low_fps_warning_title': 'Capture Performance Warning',
            'low_fps_warning_msg': 'Actual capture FPS ({actual_fps:.1f}) is lower than target FPS ({target_fps}).\n\nRecommendations:\n• Lower resolution\n• Lower quality\n• Disable overlay features\n• Close other programs',
            'mem_warning': '⚠ Memory usage is near the limit ({} / {} MB)',
            'sys_mem_low_title': 'System Memory Low',
            'sys_mem_low_msg': 'System available memory is extremely low ({}MB).\nRecording stopped automatically to prevent data loss.',
            'quit_confirm_title': 'Confirm',
            'quit_confirm_msg': 'Recording in progress. Are you sure you want to quit?',
            'save_dir_mem': 'Remember save directory',
            'save_gif': 'Save GIF',
            'save_mp4': 'Save MP4',
            'saved_to': 'Saved to: {}',
            'saved_to_path': 'File saved at:\n{}',
            'encoding_finished_msg': 'Saved: {}{}',
            'encoding_failed': 'Encoding Failed',
            'encoding_percent': 'Encoding {}... ({}%)',
            'recording_error': 'Recording Error: {}',
            'capture_no_frames_warning': 'No frames captured. Please check the capture backend.',
            'system_memory_low': 'System available memory is extremely low ({}MB).',
            'folder_open_failed': 'File saved at:\n{}',
            
            # Backend options
            'high': 'Hi',
            'medium': 'Mid',
            'low': 'Lo',
            'auto': 'Auto',
            'cpu': 'CPU',
            
            # Recording complete dialog (Integration)
            'recording_complete': 'Recording Complete',
            'recording_complete_msg': '{} frames recorded.\nWhat would you like to do?',
            'save_now': '💾 Save',
            'edit_now': '✏️ Edit',
            'discard': '🗑️ Discard',
            'opening_editor': 'Opening editor...',
            'editor_opened': 'Editor opened. Edit your recorded frames.',
            'frames_loaded': '{} frames loaded into editor.',
        }
        
        # ═══════════════════════════════════════════════════════════════
        # GIF 에디터 번역
        # ═══════════════════════════════════════════════════════════════
        self._editor_translations_ko = {
            # 메뉴
            "menu_file": "파일(&F)",
            "menu_edit": "편집(&E)",
            "menu_manage": "관리(&M)",
            "menu_settings": "설정(&T)",
            "menu_recent_files": "최근 파일(&R)",
            
            # 파일 메뉴
            "action_new": "새로 만들기(&N)",
            "action_new_tooltip": "새로운 프로젝트를 시작합니다",
            "action_open": "열기(&O)...",
            "action_open_tooltip": "GIF, 이미지, 또는 비디오 파일을 엽니다",
            "action_open_sequence": "이미지 시퀀스 열기...",
            "action_open_sequence_tooltip": "폴더의 이미지들을 순서대로 GIF로 로드합니다",
            "action_save": "저장(&S)",
            "action_save_tooltip": "현재 파일을 저장합니다",
            "action_save_as": "다른 이름으로 저장(&A)...",
            "action_save_as_tooltip": "새로운 이름과 위치로 파일을 저장합니다",
            "action_exit": "종료(&X)",
            "action_exit_tooltip": "애플리케이션을 종료합니다",
            
            # 편집 메뉴
            "action_select_all": "모두 선택(&A)",
            "action_select_all_tooltip": "모든 프레임을 선택합니다",
            "action_delete": "프레임 삭제(&D)",
            "action_delete_tooltip": "선택한 프레임을 삭제합니다",
            "action_duplicate": "프레임 복제",
            "action_duplicate_tooltip": "현재 프레임을 복제합니다",
            
            # 관리 메뉴
            "action_remove_dup": "중복 프레임 제거",
            "action_remove_dup_tooltip": "동일한 프레임을 자동으로 찾아 제거합니다",
            "action_mosaic": "모자이크/검열...",
            "action_mosaic_tooltip": "특정 영역에 모자이크 효과를 적용합니다",
            "action_speech_bubble": "말풍선...",
            "action_speech_bubble_tooltip": "말풍선을 추가하고 편집합니다",
            "action_watermark": "워터마크...",
            "action_watermark_tooltip": "이미지나 텍스트 워터마크를 추가합니다",
            "action_split_gif": "선택 프레임 분할 저장...",
            "action_split_gif_tooltip": "선택한 프레임들을 별도 GIF로 저장",
            "action_merge_gif": "GIF 끝에 병합...",
            "action_merge_gif_tooltip": "다른 GIF 파일을 현재 GIF 끝에 추가",
            "action_insert_gif": "현재 위치에 GIF 삽입...",
            "action_insert_gif_tooltip": "다른 GIF 파일을 현재 프레임 위치에 삽입",
            
            # 설정 메뉴
            "action_gpu": "GPU 가속 사용",
            "action_gpu_tooltip_available": "GPU: {name} ({memory}MB)",
            "action_gpu_tooltip_unavailable": "CUDA GPU를 찾을 수 없습니다",
            "action_gpu_info": "GPU 정보...",
            "action_gpu_info_tooltip": "GPU 하드웨어 및 사용 상태 정보를 표시합니다",
            
            # 아이콘 툴바
            "toolbar_open_file": "파일 열기 (Ctrl+O)",
            "toolbar_text": "텍스트 추가 (T)",
            "toolbar_sticker": "스티커/도형 추가",
            "toolbar_pencil": "펜슬 그리기 (P)",
            "toolbar_crop": "자르기 (C)",
            "toolbar_resize": "크기 조절 (R)",
            "toolbar_effects": "효과/필터 (E)",
            "toolbar_rotate": "90° 회전",
            "toolbar_flip_h": "좌우 뒤집기",
            "toolbar_flip_v": "상하 뒤집기",
            "toolbar_reverse": "역재생",
            "toolbar_yoyo": "요요 효과",
            "toolbar_speed": "속도 조절",
            "toolbar_reduce": "프레임 줄이기",
            
            # 도구 툴바
            "tool_select": "선택 (V)",
            "tool_crop": "자르기 (C)",
            "tool_draw": "그리기 (B)",
            "tool_text": "텍스트 (T)",
            "tool_eraser": "지우개 (E)",
            
            # 속성 패널
            "panel_frame_info": "Frame Info",
            "panel_frame": "Frame: -/-",
            "panel_size": "Size: -x-",
            "panel_timing": "Timing",
            "panel_delay": "Delay:",
            "panel_collection": "Collection",
            "panel_total_frames": "Total: 0 frames",
            "panel_duration": "Duration: 0.0s",
            
            # 프레임 리스트
            "frame_list_number": "번호",
            "frame_list_time": "프레임 시간",
            "frame_list_delete_tooltip": "선택한 프레임 삭제 (Delete)",
            "frame_list_time_tooltip": "선택한 프레임 시간 일괄 설정",
            "frame_list_add_tooltip": "프레임 복제",
            "frame_list_delete_action": "선택한 프레임 삭제",
            "frame_list_duplicate_action": "프레임 복제",
            "frame_list_select_all_action": "모두 선택",
            "frame_list_time_menu": "프레임 시간 설정",
            "frame_list_time_dialog_title": "프레임 시간 설정",
            "frame_list_time_label": "시간 (초):",
            "frame_list_apply": "적용",
            "frame_list_cancel": "취소",
            
            # 인라인 툴바 공통
            "toolbar_clear": "초기화",
            "toolbar_apply": "적용",
            "toolbar_cancel": "취소",
            
            # 속도 툴바
            "speed_playback_speed": "재생 속도",
            "speed_speed": "속도",
            "speed_result_time": "결과 시간",
            
            # 크롭 툴바
            "crop_size": "자르기 크기",
            "crop_width": "너비",
            "crop_height": "높이",
            "crop_preset": "크기 프리셋",
            "crop_preset_none": "None",
            "crop_preset_50": "50%",
            "crop_preset_75": "75%",
            "crop_preset_square": "정사각형",
            
            # 공통 적용 대상
            "target_all": "모두",
            "target_selected": "선택",
            "target_current": "현재",
            "target_tooltip": "적용 대상 프레임",
            "target_frame_hint_message": "왼쪽 프레임 창에서 효과가 적용되길 원하는 프레임을 여러 개 선택해 주세요.",

            # 말풍선 툴바
            "speech_bubble_text": "말풍선 텍스트",
            "speech_bubble_text_placeholder": "텍스트를 입력하세요",
            "speech_bubble_font_size": "폰트 크기",
            "speech_bubble_style": "말풍선 스타일",
            "speech_bubble_tail": "꼬리 방향",
            "speech_bubble_bg_color": "배경색",
            "speech_bubble_text_color": "텍스트 색상",
            "dont_show_again": "다음 부터 안보기",
            
            # 효과 툴바
            "effects_brightness": "밝기",
            "effects_contrast": "대비",
            "effects_saturation": "채도",
            "effects_filter": "필터",
            "effects_filter_none": "없음",
            "effects_filter_grayscale": "흑백",
            "effects_filter_sepia": "세피아",
            "effects_filter_invert": "반전",
            "effects_filter_blur": "블러",
            "effects_filter_sharpen": "샤픈",
            "effects_filter_emboss": "엠보스",
            "effects_filter_contour": "윤곽선",
            "effects_filter_posterize": "포스터",
            "effects_filter_vignette": "비네트",
            
            # 텍스트 툴바
            "text_input": "텍스트 입력",
            "text_placeholder": "텍스트",
            "text_font_size": "폰트 크기",
            "text_font_select": "폰트 선택",
            "text_color": "텍스트 색상",
            "text_outline": "텍스트 테두리",
            "text_outline_width": "외곽선 두께",
            "text_animation": "애니메이션 효과",
            "text_blink": "깜빡임 효과",
            "text_blink_interval": "깜빡임 간격",
            
            # 스티커 툴바
            "sticker_shape": "스티커 도형",
            "sticker_size": "스티커 크기",
            "sticker_size_tooltip": "크기",
            "sticker_fill_color": "채우기 색상",
            "sticker_dialog_title": "스티커/도형 추가",
            "shape_rectangle": "사각형",
            "shape_ellipse": "원",
            "shape_triangle": "삼각형",
            "shape_star": "별",
            "shape_arrow": "화살표",
            "shape_heart": "하트",
            
            # 버튼
            "btn_save": "저장",
            "btn_close_edit": "편집 종료",
            
            # 워터마크 툴바
            "watermark_type": "워터마크 타입",
            "watermark_type_text": "텍스트",
            "watermark_type_image": "이미지",
            "watermark_type_tooltip": "타입",
            "watermark_text_placeholder": "텍스트",
            "watermark_font_size": "폰트 크기",
            "watermark_text_color": "텍스트 색상",
            "watermark_image_btn": "이미지",
            
            # 프레임 줄이기 툴바
            "reduce_keep": "N개마다 1개 유지",
            "reduce_tooltip": "N개마다 1개만 유지 (예: 2 = 2개 중 1개만 유지)",
            
            # 리사이즈 툴바
            "resize_width_height": "너비, 높이",
            "resize_width": "너비",
            "resize_height": "높이",
            "resize_keep_ratio": "비율 유지",
            "resize_preset": "크기 프리셋",
            "resize_filter": "리샘플링 필터",
            
            # 정보 바
            "info_size": "영상 크기: {size}",
            "info_size_empty": "영상 크기: -",
            "info_frame_count": "프레임 수: {count}",
            "info_frame_count_empty": "프레임 수: 0",
            "info_duration": "재생 시간: {duration}초",
            "info_duration_empty": "재생 시간: 0.00초",
            "info_size_tooltip": "이미지 크기 (가로x세로)",
            "info_frame_count_tooltip": "총 프레임 수",
            "info_duration_tooltip": "총 재생 시간",
            "info_memory_tooltip": "메모리 사용량 (300MB 이상: 주의, 500MB 이상: 경고)",
            "btn_close_edit_tooltip": "에디터를 닫습니다",
            "btn_save_tooltip": "파일을 저장합니다 (Ctrl+Shift+S)",
            "btn_play_tooltip": "재생/일시정지 (Space)",
            "btn_pause_tooltip": "일시정지 (Space)",

            # 최근 파일 메뉴
            "recent_files_none": "(없음)",
            "recent_files_clear": "목록 지우기",
            "recent_files_clear_tooltip": "최근 파일 목록을 모두 지웁니다",
            
            # 언어 토글
            "lang_toggle_tooltip": "언어 전환 (한국어/영어)",
            
            # 메시지 박스
            "msg_error": "오류",
            "msg_warning": "경고",
            "msg_info": "정보",
            "msg_complete": "완료",
            "msg_confirm": "확인",
            "msg_save": "저장",
            "msg_discard": "버리기",
            "msg_cancel": "취소",
            "msg_yes": "예",
            "msg_no": "아니오",
            
            # 파일 관련 메시지
            "msg_file_open_error": "파일을 열 수 없습니다",
            "msg_large_file_warning_title": "대용량 파일",
            "msg_large_file_warning_msg": "프레임 {count}개, 예상 메모리 약 {memory:.0f}MB입니다. 메모리 부족으로 불안정할 수 있습니다. 계속 열까요?",
            "msg_file_not_found": "파일을 찾을 수 없습니다",
            "msg_file_save_error": "저장 실패",
            "msg_file_save_complete": "파일이 저장되었습니다",
            "msg_no_frames_to_save": "저장할 프레임이 없습니다",
            "msg_no_gif_open": "열린 GIF가 없습니다",
            "msg_no_gif_file": "열린 GIF 파일이 없습니다",
            "msg_select_frames_to_split": "분할할 프레임을 선택해주세요",
            "msg_load_complete": "로드 완료",
            "msg_image_sequence_loaded": "이미지 시퀀스가 로드되었습니다",
            "msg_frames_count": "프레임 수: {count}개",
            
            # 비디오 관련 메시지
            "msg_video_info_error": "비디오 파일 정보를 읽을 수 없습니다",
            "msg_video_convert_complete": "변환 완료",
            "msg_video_convert_error": "비디오 변환 실패",
            "msg_video_converting": "비디오 변환 중...",
            "msg_video_to_gif": "비디오 → GIF 변환",
            
            # 저장 관련 메시지
            "msg_save_progress": "GIF 저장",
            "msg_save_complete": "저장 완료",
            "msg_file_size": "크기: {size} KB",
            "msg_unsaved_changes": "저장하지 않은 변경 사항이 있습니다",
            "msg_save_before_close": "저장하시겠습니까?",
            
            # 프레임 관련 메시지
            "msg_frame_duplicate_complete": "프레임이 복제되었습니다",
            "msg_frame_duplicate_error": "프레임 복제 실패",
            "msg_frame_duplicate_undo_error": "실행 취소 실패",
            "msg_frame_duplicate_error2": "프레임 복제 중 오류가 발생했습니다",
            "msg_frame_reduce_error": "프레임 감소 실패",
            "msg_frame_reduce_error2": "프레임 감소 중 오류가 발생했습니다",
            "msg_duplicate_removed": "{count}개의 중복 프레임이 제거되었습니다",
            "msg_duplicate_remove_error": "중복 프레임 제거 실패",
            "msg_duplicate_remove_error2": "중복 프레임 제거 중 오류가 발생했습니다",
            "msg_memory_limit": "메모리 사용량이 커서 실행 취소 기능을 사용할 수 없습니다: {memory}MB",
            "msg_min_frames_required": "최소 1개의 프레임은 남겨야 합니다",
            "msg_select_frames": "적용할 프레임을 선택하세요",
            "msg_current_frame_only": "현재 프레임만으로는 줄이기를 할 수 없습니다",
            "msg_use_all_or_selected": "'모두' 또는 '선택' 옵션을 사용하세요",
            "msg_frames_reduced": "{removed}개 프레임이 제거되었습니다",
            "msg_frames_remaining": "남은 프레임: {count}개",
            
            # 분할/병합/삽입 메시지
            "msg_split_error": "분할 저장 중 오류가 발생했습니다",
            "msg_split_complete": "완료",
            "msg_split_files_saved": "{count}개의 파일이 저장되었습니다",
            "msg_merge_error": "병합 중 오류가 발생했습니다",
            "msg_merge_complete": "완료",
            "msg_frames_merged": "{count}개의 프레임이 병합되었습니다",
            "msg_insert_error": "삽입 중 오류가 발생했습니다",
            "msg_insert_complete": "완료",
            "msg_frames_inserted": "{count}개의 프레임이 삽입되었습니다",
            "msg_gif_load_error": "GIF 로드 실패",
            "msg_gif_loading": "GIF 로드 중...",
            
            # 속도/딜레이 메시지
            "msg_speed_error": "속도 조절 실패",
            "msg_speed_error2": "속도 조절 중 오류가 발생했습니다",
            "msg_delay_error": "딜레이 설정 실패",
            "msg_delay_error2": "딜레이 설정 중 오류가 발생했습니다",
            "msg_all_frames_delay": "모든 프레임 시간 설정",
            "msg_all_frames_delay_label": "모든 프레임의 시간 (밀리초):",
            "msg_frame_delay": "프레임 딜레이",
            "msg_frame_delay_label": "딜레이 (밀리초):",
            
            # 회전/뒤집기 메시지
            "msg_rotate_error": "프레임 회전 실패",
            "msg_rotate_error2": "프레임 회전 중 오류가 발생했습니다",
            "msg_flip_error": "프레임 뒤집기 실패",
            "msg_flip_error2": "프레임 뒤집기 중 오류가 발생했습니다",
            
            # 효과 메시지
            "msg_reverse_complete": "프레임 순서가 반전되었습니다",
            "msg_reverse_error": "프레임 순서 반전 실패",
            "msg_reverse_error2": "프레임 순서 반전 중 오류가 발생했습니다",
            "msg_yoyo_complete": "요요 효과가 적용되었습니다",
            "msg_yoyo_error": "요요 효과 적용 실패",
            "msg_yoyo_error2": "요요 효과 적용 중 오류가 발생했습니다",
            
            # GPU 메시지
            "msg_gpu_accel": "GPU 가속",
            "msg_gpu_enabled": "GPU 가속이 활성화되었습니다",
            "msg_gpu_disabled": "GPU 가속이 비활성화되었습니다",
            "msg_gpu_info": "GPU 정보",
            "msg_gpu_info_detail": "GPU 정보:\n\n이름: {name}\n메모리: {memory} MB\nCompute Capability: {capability}\n현재 상태: {status}\n\nGPU 가속 지원 기능:\n• 세피아 효과\n• 비네트 효과\n• 색조(Hue) 조절\n• 프레임 유사도 계산",
            "msg_gpu_not_found": "CUDA GPU를 찾을 수 없습니다",
            "msg_gpu_requirements": "GPU 가속을 사용하려면:\n1. NVIDIA GPU가 필요합니다\n2. CUDA Toolkit이 설치되어 있어야 합니다\n3. CuPy 라이브러리가 필요합니다\n   (pip install cupy-cuda12x)",
            
            # GPU 툴팁
            "gpu_tooltip_mode": "모드: {mode}",
            "gpu_tooltip_gpu": "GPU: {name}",
            "gpu_tooltip_memory": "메모리: {total} MB",
            "gpu_tooltip_memory_used": "사용 중: {used} MB",
            "gpu_tooltip_memory_free": "여유: {free} MB",
            "gpu_tooltip_cuda": "CUDA: {version}",
            "gpu_tooltip_compute": "Compute: {capability}",
            "gpu_tooltip_error": "오류: {error}",
            "gpu_tooltip_unavailable": "GPU를 사용할 수 없습니다",
            "gpu_tooltip_requirements": "CuPy 설치 필요: pip install cupy-cuda12x",

            # CuPy 설치
            "cupy_install_title": "CuPy GPU 가속 설치",
            "cupy_install_msg": "NVIDIA GPU가 감지되었지만 CuPy가 설치되어 있지 않습니다.\n\n"
                "감지된 CUDA 드라이버: {cuda_version}\n"
                "설치할 패키지: {package}\n\n"
                "GPU 가속(세피아, 비네트, 색조 조절 등)을 사용하려면\n"
                "CuPy를 설치해야 합니다.\n\n"
                "지금 설치하시겠습니까? (인터넷 필요, 수 분 소요)",
            "cupy_installing": "{package} 설치 중... 잠시 기다려주세요 (수 분 소요될 수 있습니다).",
            "cupy_install_success": "CuPy가 성공적으로 설치되었습니다!\nGPU 가속을 사용할 수 있습니다.",
            "cupy_install_failed": "CuPy 설치에 실패했습니다.\n\n오류: {}",
            "cupy_cuda_detect_failed": "CUDA 드라이버 버전을 감지할 수 없습니다.\n\n"
                "NVIDIA 드라이버가 올바르게 설치되어 있는지 확인해주세요.\n"
                "수동 설치: pip install cupy-cuda12x",

            # 메모리 관련 메시지
            "msg_memory_error": "메모리가 부족하여 작업을 수행할 수 없습니다",
            
            # 펜슬 관련 메시지
            "msg_pencil_no_lines": "그린 선이 없습니다",
            "msg_pencil_no_frames": "적용할 프레임이 없습니다",
            "msg_pencil_apply": "프레임에 적용",
            "msg_pencil_cancel": "펜슬 모드 취소",
            
            # 저장 다이얼로그
            "save_dialog_title": "GIF 저장 설정",
            "save_dialog_preview": "미리보기",
            "save_dialog_zoom": "Zoom:",
            "save_dialog_frame": "프레임:",
            "save_dialog_preview_info": "원본 vs 압축 미리보기",
            "save_dialog_quantization": "양자화 알고리즘",
            "save_dialog_quant_adaptive": "ADAPTIVE (기본)",
            "save_dialog_quant_median": "MEDIAN CUT",
            "save_dialog_quant_max": "MAX COVERAGE",
            "save_dialog_quant_octree": "FAST OCTREE",
            "save_dialog_quant_liq": "LIBIMAGEQUANT (LIQ)",
            "save_dialog_quant_desc": "PIL 기본 양자화 알고리즘",
            "save_dialog_quality": "품질 설정",
            "save_dialog_colors": "색상 수",
            "save_dialog_dither": "디더링 사용",
            "save_dialog_optimize": "파일 크기 최적화",
            "save_dialog_result": "예상 결과",
            "save_dialog_size": "예상 크기:",
            "save_dialog_save": "저장",
            "save_dialog_cancel": "취소",
            
            # 기타
            "lang_en": "En",
            "lang_kr": "한",
        }
        
        self._editor_translations_en = {
            # 메뉴
            "menu_file": "File(&F)",
            "menu_edit": "Edit(&E)",
            "menu_manage": "Manage(&M)",
            "menu_settings": "Settings(&T)",
            "menu_recent_files": "Recent Files(&R)",
            
            # 파일 메뉴
            "action_new": "New(&N)",
            "action_new_tooltip": "Start a new project",
            "action_open": "Open(&O)...",
            "action_open_tooltip": "Open GIF, image, or video file",
            "action_open_sequence": "Open Image Sequence...",
            "action_open_sequence_tooltip": "Load images from a folder in order as GIF",
            "action_save": "Save(&S)",
            "action_save_tooltip": "Save the current file",
            "action_save_as": "Save As(&A)...",
            "action_save_as_tooltip": "Save file with a new name and location",
            "action_exit": "Exit(&X)",
            "action_exit_tooltip": "Exit the application",
            
            # 편집 메뉴
            "action_select_all": "Select All(&A)",
            "action_select_all_tooltip": "Select all frames",
            "action_delete": "Delete Frame(&D)",
            "action_delete_tooltip": "Delete selected frames",
            "action_duplicate": "Duplicate Frame",
            "action_duplicate_tooltip": "Duplicate the current frame",
            
            # 관리 메뉴
            "action_remove_dup": "Remove Duplicate Frames",
            "action_remove_dup_tooltip": "Automatically find and remove identical frames",
            "action_mosaic": "Mosaic/Censor...",
            "action_mosaic_tooltip": "Apply mosaic effect to specific areas",
            "action_speech_bubble": "Speech Bubble...",
            "action_speech_bubble_tooltip": "Add and edit speech bubbles",
            "action_watermark": "Watermark...",
            "action_watermark_tooltip": "Add image or text watermark",
            "action_split_gif": "Split Selected Frames...",
            "action_split_gif_tooltip": "Save selected frames as separate GIF",
            "action_merge_gif": "Merge GIF at End...",
            "action_merge_gif_tooltip": "Add another GIF file to the end of current GIF",
            "action_insert_gif": "Insert GIF at Current Position...",
            "action_insert_gif_tooltip": "Insert another GIF file at current frame position",
            
            # 설정 메뉴
            "action_gpu": "Use GPU Acceleration",
            "action_gpu_tooltip_available": "GPU: {name} ({memory}MB)",
            "action_gpu_tooltip_unavailable": "CUDA GPU not found",
            "action_gpu_info": "GPU Info...",
            "action_gpu_info_tooltip": "Display GPU hardware and usage information",
            
            # 아이콘 툴바
            "toolbar_open_file": "Open File (Ctrl+O)",
            "toolbar_text": "Add Text (T)",
            "toolbar_sticker": "Add Sticker/Shape",
            "toolbar_pencil": "Draw with Pencil (P)",
            "toolbar_crop": "Crop (C)",
            "toolbar_resize": "Resize (R)",
            "toolbar_effects": "Effects/Filters (E)",
            "toolbar_rotate": "Rotate 90°",
            "toolbar_flip_h": "Flip Horizontal",
            "toolbar_flip_v": "Flip Vertical",
            "toolbar_reverse": "Reverse Playback",
            "toolbar_yoyo": "Yoyo Effect",
            "toolbar_speed": "Speed Control",
            "toolbar_reduce": "Reduce Frames",
            
            # 도구 툴바
            "tool_select": "Select (V)",
            "tool_crop": "Crop (C)",
            "tool_draw": "Draw (B)",
            "tool_text": "Text (T)",
            "tool_eraser": "Eraser (E)",
            
            # 속성 패널
            "panel_frame_info": "Frame Info",
            "panel_frame": "Frame: -/-",
            "panel_size": "Size: -x-",
            "panel_timing": "Timing",
            "panel_delay": "Delay:",
            "panel_collection": "Collection",
            "panel_total_frames": "Total: 0 frames",
            "panel_duration": "Duration: 0.0s",
            
            # 프레임 리스트
            "frame_list_number": "No.",
            "frame_list_time": "Frame Time",
            "frame_list_delete_tooltip": "Delete Selected Frames (Delete)",
            "frame_list_time_tooltip": "Set Time for Selected Frames",
            "frame_list_add_tooltip": "Duplicate Frame",
            "frame_list_delete_action": "Delete Selected Frames",
            "frame_list_duplicate_action": "Duplicate Frame",
            "frame_list_select_all_action": "Select All",
            "frame_list_time_menu": "Set Frame Time",
            "frame_list_time_dialog_title": "Set Frame Time",
            "frame_list_time_label": "Time (seconds):",
            "frame_list_apply": "Apply",
            "frame_list_cancel": "Cancel",
            
            # 인라인 툴바 공통
            "toolbar_clear": "Clear",
            "toolbar_apply": "Apply",
            "toolbar_cancel": "Cancel",
            
            # 속도 툴바
            "speed_playback_speed": "Playback Speed",
            "speed_speed": "Speed",
            "speed_result_time": "Result Time",
            
            # 크롭 툴바
            "crop_size": "Crop Size",
            "crop_width": "Width",
            "crop_height": "Height",
            "crop_preset": "Size Preset",
            "crop_preset_none": "None",
            "crop_preset_50": "50%",
            "crop_preset_75": "75%",
            "crop_preset_square": "Square",
            
            # 공통 적용 대상
            "target_all": "All",
            "target_selected": "Selected",
            "target_current": "Current",
            "target_tooltip": "Target Frames",
            "target_frame_hint_message": "Please select multiple frames in the left frame pane where you want the effect to be applied.",

            # Speech Bubble Toolbar
            "speech_bubble_text": "Bubble Text",
            "speech_bubble_text_placeholder": "Enter text",
            "speech_bubble_font_size": "Font Size",
            "speech_bubble_style": "Bubble Style",
            "speech_bubble_tail": "Tail Direction",
            "speech_bubble_bg_color": "Background Color",
            "speech_bubble_text_color": "Text Color",
            "dont_show_again": "Don't show again",
            
            # 효과 툴바
            "effects_brightness": "Brightness",
            "effects_contrast": "Contrast",
            "effects_saturation": "Saturation",
            "effects_filter": "Filter",
            "effects_filter_none": "None",
            "effects_filter_grayscale": "Grayscale",
            "effects_filter_sepia": "Sepia",
            "effects_filter_invert": "Invert",
            "effects_filter_blur": "Blur",
            "effects_filter_sharpen": "Sharpen",
            "effects_filter_emboss": "Emboss",
            "effects_filter_contour": "Contour",
            "effects_filter_posterize": "Posterize",
            "effects_filter_vignette": "Vignette",
            
            # 텍스트 툴바
            "text_input": "Text Input",
            "text_placeholder": "Text",
            "text_font_size": "Font Size",
            "text_font_select": "Font",
            "text_color": "Text Color",
            "text_outline": "Text Outline",
            "text_outline_width": "Outline Width",
            "text_animation": "Animation Effect",
            "text_blink": "Blink Effect",
            "text_blink_interval": "Blink Interval",
            
            # 스티커 툴바
            "sticker_shape": "Sticker/Shape",
            "sticker_size": "Sticker Size",
            "sticker_size_tooltip": "Size",
            "sticker_fill_color": "Fill Color",
            "sticker_dialog_title": "Add Sticker/Shape",
            "shape_rectangle": "Rectangle",
            "shape_ellipse": "Ellipse",
            "shape_triangle": "Triangle",
            "shape_star": "Star",
            "shape_arrow": "Arrow",
            "shape_heart": "Heart",
            
            # 버튼
            "btn_save": "Save",
            "btn_close_edit": "Finish Editing",
            
            # 워터마크 툴바
            "watermark_type": "Watermark Type",
            "watermark_type_text": "Text",
            "watermark_type_image": "Image",
            "watermark_type_tooltip": "Type",
            "watermark_text_placeholder": "Text",
            "watermark_font_size": "Font Size",
            "watermark_text_color": "Text Color",
            "watermark_image_btn": "Image",
            
            # 프레임 줄이기 툴바
            "reduce_keep": "Keep 1 of N",
            "reduce_tooltip": "Keep 1 of N frames (e.g., 2 = keep 1 of every 2)",
            
            # 리사이즈 툴바
            "resize_width_height": "Width, Height",
            "resize_width": "Width",
            "resize_height": "Height",
            "resize_keep_ratio": "Keep Aspect Ratio",
            "resize_preset": "Size Preset",
            "resize_filter": "Resampling Filter",
            
            # 정보 바
            "info_size": "Size: {size}",
            "info_size_empty": "Size: -",
            "info_frame_count": "Frames: {count}",
            "info_frame_count_empty": "Frames: 0",
            "info_duration": "Duration: {duration}s",
            "info_duration_empty": "Duration: 0.00s",
            "info_size_tooltip": "Image size (Width x Height)",
            "info_frame_count_tooltip": "Total frame count",
            "info_duration_tooltip": "Total playback duration",
            "info_memory_tooltip": "Memory usage (300MB+: caution, 500MB+: warning)",
            "btn_close_edit_tooltip": "Close the editor",
            "btn_save_tooltip": "Save file (Ctrl+Shift+S)",
            "btn_play_tooltip": "Play/Pause (Space)",
            "btn_pause_tooltip": "Pause (Space)",

            # 최근 파일 메뉴
            "recent_files_none": "(None)",
            "recent_files_clear": "Clear List",
            "recent_files_clear_tooltip": "Clear all recent files",
            
            # 언어 토글
            "lang_toggle_tooltip": "Toggle Language (Korean/English)",
            
            # 메시지 박스
            "msg_error": "Error",
            "msg_warning": "Warning",
            "msg_info": "Information",
            "msg_complete": "Complete",
            "msg_confirm": "Confirm",
            "msg_save": "Save",
            "msg_discard": "Discard",
            "msg_cancel": "Cancel",
            "msg_yes": "Yes",
            "msg_no": "No",
            
            # 파일 관련 메시지
            "msg_file_open_error": "Cannot open file",
            "msg_large_file_warning_title": "Large File",
            "msg_large_file_warning_msg": "This file has {count} frames and may use about {memory:.0f}MB of memory. Opening it may cause instability. Continue?",
            "msg_file_not_found": "File not found",
            "msg_file_save_error": "Save failed",
            "msg_file_save_complete": "File saved successfully",
            "msg_no_frames_to_save": "No frames to save",
            "msg_no_gif_open": "No GIF file is open",
            "msg_no_gif_file": "No GIF file is open",
            "msg_select_frames_to_split": "Please select frames to split",
            "msg_load_complete": "Load Complete",
            "msg_image_sequence_loaded": "Image sequence loaded successfully",
            "msg_frames_count": "Frames: {count}",
            
            # 비디오 관련 메시지
            "msg_video_info_error": "Cannot read video file information",
            "msg_video_convert_complete": "Conversion Complete",
            "msg_video_convert_error": "Video conversion failed",
            "msg_video_converting": "Converting video...",
            "msg_video_to_gif": "Video → GIF Conversion",
            
            # 저장 관련 메시지
            "msg_save_progress": "Saving GIF",
            "msg_save_complete": "Save Complete",
            "msg_file_size": "Size: {size} KB",
            "msg_unsaved_changes": "You have unsaved changes",
            "msg_save_before_close": "Do you want to save?",
            
            # 프레임 관련 메시지
            "msg_frame_duplicate_complete": "Frame duplicated",
            "msg_frame_duplicate_error": "Frame duplication failed",
            "msg_frame_duplicate_undo_error": "Undo failed",
            "msg_frame_duplicate_error2": "Error occurred while duplicating frame",
            "msg_frame_reduce_error": "Frame reduction failed",
            "msg_frame_reduce_error2": "Error occurred while reducing frames",
            "msg_duplicate_removed": "{count} duplicate frames removed",
            "msg_duplicate_remove_error": "Duplicate removal failed",
            "msg_duplicate_remove_error2": "Error occurred while removing duplicates",
            "msg_memory_limit": "Cannot use undo due to high memory usage: {memory}MB",
            "msg_min_frames_required": "At least 1 frame must remain",
            "msg_select_frames": "Please select frames to apply",
            "msg_current_frame_only": "Cannot reduce with current frame only",
            "msg_use_all_or_selected": "Please use 'All' or 'Selected' option",
            "msg_frames_reduced": "{removed} frames removed",
            "msg_frames_remaining": "Remaining frames: {count}",
            
            # 분할/병합/삽입 메시지
            "msg_split_error": "Error occurred while splitting",
            "msg_split_complete": "Complete",
            "msg_split_files_saved": "{count} files saved",
            "msg_merge_error": "Error occurred while merging",
            "msg_merge_complete": "Complete",
            "msg_frames_merged": "{count} frames merged",
            "msg_insert_error": "Error occurred while inserting",
            "msg_insert_complete": "Complete",
            "msg_frames_inserted": "{count} frames inserted",
            "msg_gif_load_error": "GIF load failed",
            "msg_gif_loading": "Loading GIF...",
            
            # 속도/딜레이 메시지
            "msg_speed_error": "Speed adjustment failed",
            "msg_speed_error2": "Error occurred while adjusting speed",
            "msg_delay_error": "Delay setting failed",
            "msg_delay_error2": "Error occurred while setting delay",
            "msg_all_frames_delay": "Set All Frames Delay",
            "msg_all_frames_delay_label": "Delay for all frames (milliseconds):",
            "msg_frame_delay": "Frame Delay",
            "msg_frame_delay_label": "Delay (milliseconds):",
            
            # 회전/뒤집기 메시지
            "msg_rotate_error": "Frame rotation failed",
            "msg_rotate_error2": "Error occurred while rotating frames",
            "msg_flip_error": "Frame flip failed",
            "msg_flip_error2": "Error occurred while flipping frames",
            
            # 효과 메시지
            "msg_reverse_complete": "Frame order reversed",
            "msg_reverse_error": "Frame reverse failed",
            "msg_reverse_error2": "Error occurred while reversing frames",
            "msg_yoyo_complete": "Yoyo effect applied",
            "msg_yoyo_error": "Yoyo effect application failed",
            "msg_yoyo_error2": "Error occurred while applying yoyo effect",
            
            # GPU 메시지
            "msg_gpu_accel": "GPU Acceleration",
            "msg_gpu_enabled": "GPU acceleration enabled",
            "msg_gpu_disabled": "GPU acceleration disabled",
            "msg_gpu_info": "GPU Info",
            "msg_gpu_info_detail": "GPU Information:\n\nName: {name}\nMemory: {memory} MB\nCompute Capability: {capability}\nCurrent Status: {status}\n\nGPU Acceleration Supported Features:\n• Sepia effect\n• Vignette effect\n• Hue adjustment\n• Frame similarity calculation",
            "msg_gpu_not_found": "CUDA GPU not found",
            "msg_gpu_requirements": "To use GPU acceleration:\n1. NVIDIA GPU is required\n2. CUDA Toolkit must be installed\n3. CuPy library is required\n   (pip install cupy-cuda12x)",
            
            # GPU 툴팁
            "gpu_tooltip_mode": "Mode: {mode}",
            "gpu_tooltip_gpu": "GPU: {name}",
            "gpu_tooltip_memory": "Memory: {total} MB",
            "gpu_tooltip_memory_used": "Used: {used} MB",
            "gpu_tooltip_memory_free": "Free: {free} MB",
            "gpu_tooltip_cuda": "CUDA: {version}",
            "gpu_tooltip_compute": "Compute: {capability}",
            "gpu_tooltip_error": "Error: {error}",
            "gpu_tooltip_unavailable": "GPU unavailable",
            "gpu_tooltip_requirements": "CuPy installation required: pip install cupy-cuda12x",

            # CuPy installation
            "cupy_install_title": "Install CuPy GPU Acceleration",
            "cupy_install_msg": "NVIDIA GPU detected but CuPy is not installed.\n\n"
                "Detected CUDA driver: {cuda_version}\n"
                "Package to install: {package}\n\n"
                "CuPy is required for GPU acceleration\n"
                "(sepia, vignette, hue shift, etc.).\n\n"
                "Would you like to install it now? (Internet required, may take several minutes)",
            "cupy_installing": "Installing {package}... Please wait (this may take several minutes).",
            "cupy_install_success": "CuPy has been installed successfully!\nGPU acceleration is now available.",
            "cupy_install_failed": "Failed to install CuPy.\n\nError: {}",
            "cupy_cuda_detect_failed": "Could not detect CUDA driver version.\n\n"
                "Please ensure NVIDIA drivers are properly installed.\n"
                "Manual install: pip install cupy-cuda12x",

            # 메모리 관련 메시지
            "msg_memory_error": "Insufficient memory to perform the operation",
            
            # 펜슬 관련 메시지
            "msg_pencil_no_lines": "No lines drawn",
            "msg_pencil_no_frames": "No frames to apply",
            "msg_pencil_apply": "Apply to Frames",
            "msg_pencil_cancel": "Cancel Pencil Mode",
            
            # 저장 다이얼로그
            "save_dialog_title": "GIF Save Settings",
            "save_dialog_preview": "Preview",
            "save_dialog_zoom": "Zoom:",
            "save_dialog_frame": "Frame:",
            "save_dialog_preview_info": "Original vs Compressed Preview",
            "save_dialog_quantization": "Quantization Algorithm",
            "save_dialog_quant_adaptive": "ADAPTIVE (Default)",
            "save_dialog_quant_median": "MEDIAN CUT",
            "save_dialog_quant_max": "MAX COVERAGE",
            "save_dialog_quant_octree": "FAST OCTREE",
            "save_dialog_quant_liq": "LIBIMAGEQUANT (LIQ)",
            "save_dialog_quant_desc": "PIL default quantization algorithm",
            "save_dialog_quality": "Quality Settings",
            "save_dialog_colors": "Number of Colors",
            "save_dialog_dither": "Use Dithering",
            "save_dialog_optimize": "Optimize File Size",
            "save_dialog_result": "Expected Result",
            "save_dialog_size": "Estimated Size:",
            "save_dialog_save": "Save",
            "save_dialog_cancel": "Cancel",
            
            # 기타
            "lang_en": "En",
            "lang_kr": "한",
        }
        
        # 통합 번역 딕셔너리 생성
        self._translations = {
            'ko': {**self._main_translations_ko, **self._editor_translations_ko},
            'en': {**self._main_translations_en, **self._editor_translations_en}
        }
        
    def set_language(self, lang: str):
        """언어 설정 (ko 또는 en)"""
        if lang in self._translations and lang != self._current_lang:
            self._current_lang = lang
            # 모든 콜백 호출
            for callback in list(self._callbacks):
                try:
                    callback(lang)
                except Exception:
                    pass
    
    def register_callback(self, callback: Callable[[str], None]):
        """언어 변경 콜백 등록"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def unregister_callback(self, callback: Callable[[str], None]):
        """언어 변경 콜백 제거"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            
    @property
    def current_lang(self) -> str:
        return self._current_lang
        
    def get_language(self) -> str:
        return self._current_lang
    
    @property
    def is_korean(self) -> bool:
        """현재 언어가 한국어인지 반환 (에디터 호환)"""
        return self._current_lang == 'ko'
        
    def get(self, key: str, default: str = None, **kwargs) -> str:
        """Get translated string for the current language
        
        Args:
            key: 번역 키
            default: 키가 없을 때 기본값
            **kwargs: 포맷 문자열에 사용할 인자들
            
        Returns:
            번역된 텍스트
        """
        text = self._translations[self._current_lang].get(key, default if default is not None else key)
        
        # 포맷 문자열 처리
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        
        return text


# ═══════════════════════════════════════════════════════════════
# 공용 함수 및 싱글톤 접근자
# ═══════════════════════════════════════════════════════════════

def get_trans_manager() -> TranslationManager:
    """TranslationManager 싱글톤 인스턴스 반환"""
    return TranslationManager.instance()


def tr(key: str, default: str = None, **kwargs) -> str:
    """번역 함수 (메인 앱용)
    
    Args:
        key: 번역 키
        default: 키가 없을 때 기본값
        **kwargs: 포맷 문자열에 사용할 인자들
        
    Returns:
        번역된 텍스트
    """
    return TranslationManager.instance().get(key, default, **kwargs)


# ═══════════════════════════════════════════════════════════════
# 에디터 호환 래퍼 클래스
# ═══════════════════════════════════════════════════════════════

class EditorTranslations:
    """GIF 에디터 호환용 래퍼 클래스
    
    기존 editor/utils/translations.py의 Translations 클래스와
    동일한 인터페이스를 제공합니다.
    """
    
    def __init__(self, is_korean: bool = True):
        """초기화
        
        Args:
            is_korean: True면 한국어, False면 영어
        """
        self._manager = get_trans_manager()
        if is_korean:
            self._manager.set_language('ko')
        else:
            self._manager.set_language('en')
    
    def tr(self, key: str, **kwargs) -> str:
        """번역 텍스트 반환
        
        Args:
            key: 번역 키
            **kwargs: 포맷 문자열에 사용할 인자들
            
        Returns:
            번역된 텍스트
        """
        return self._manager.get(key, **kwargs)
    
    def set_language(self, is_korean: bool):
        """언어 설정
        
        Args:
            is_korean: True면 한국어, False면 영어
        """
        self._manager.set_language('ko' if is_korean else 'en')
    
    @property
    def is_korean(self) -> bool:
        """현재 언어가 한국어인지 반환"""
        return self._manager.is_korean


# 하위 호환성을 위한 별칭
Translations = EditorTranslations
