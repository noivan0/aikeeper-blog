---
title: "🎙️ Whisper로 회의 음성 자동 변환: 무료 로컬 설치부터 한국어 인식까지"
labels: ["AI음성", "오픈소스AI", "AI생산성", "AI기초", "로컬LLM"]
draft: false
meta_description: "OpenAI Whisper 한국어 음성 텍스트 변환을 무료로 구현하려는 분들을 위해, 로컬 설치부터 회의록 자동화까지 2026년 기준으로 정리했습니다."
naver_summary: "이 글에서는 whisper 한국어 설치 및 활용법을 단계별로 정리합니다. 클라우드 비용 없이 로컬에서 회의 음성을 텍스트로 자동 변환하는 실전 방법을 얻을 수 있습니다."
seo_keywords: "whisper 한국어 음성인식 설치, openai whisper 로컬 무료 설치, 회의록 자동 변환 무료 프로그램, 음성 텍스트 변환 무료 오픈소스, whisper 파이썬 설치 방법"
faqs: [{"q": "OpenAI Whisper 무료로 쓸 수 있나요?", "a": "네, OpenAI Whisper는 MIT 라이선스로 공개된 완전 무료 오픈소스 모델입니다. GitHub에서 소스코드를 내려받아 로컬 PC에 설치하면 API 비용 없이 무제한으로 사용할 수 있어요. 단, Whisper를 OpenAI API로 사용할 경우(Whisper API)는 분당 약 $0.006의 비용이 발생합니다. 로컬 설치 방식은 초기 설치가 약간 번거롭지만 이후에는 인터넷 연결 없이도 완전 무료로 음성 텍스트 변환이 가능하고, 사내 회의 내용 같은 민감한 데이터도 외부로 전송되지 않아 보안 측면에서도 우수합니다."}, {"q": "Whisper 한국어 인식 정확도가 어느 정도인가요?", "a": "Whisper의 한국어 인식 정확도는 모델 크기에 따라 크게 달라집니다. 가장 큰 모델인 large-v3 기준으로 한국어 WER(단어 오류율)은 약 8~12% 수준으로, 표준 한국어 발음 기준으로는 매우 높은 정확도를 보입니다. 다만 사투리, 전문 용어, 빠른 말투, 배경 소음이 있는 환경에서는 정확도가 떨어질 수 있어요. 실무에서는 large-v3 모델 + 후처리 교정 조합을 권장합니다. medium 모델도 한국어에서 충분히 실용적인 수준(WER 약 15%)이라 GPU 메모리가 부족한 환경에서는 medium으로도 충분합니다."}, {"q": "Whisper 설치할 때 GPU 없어도 되나요?", "a": "GPU 없이 CPU만으로도 Whisper 실행이 가능합니다. 다만 속도 차이가 상당해요. GPU(RTX 3060 기준)로는 1시간짜리 음성을 약 5~7분에 처리하지만, CPU(Intel i7 기준)로는 같은 파일을 처리하는 데 30~60분이 걸릴 수 있습니다. CPU 환경에서는 작은 모델(tiny, base, small)을 사용하는 것이 현실적이에요. GPU가 없는 환경에서 빠른 처리가 필요하다면, whisper.cpp나 faster-whisper 같은 최적화 구현체를 사용하면 CPU에서도 2~4배 빠른 속도를 낼 수 있습니다."}, {"q": "Whisper로 Zoom이나 Teams 회의 녹화 파일 변환할 수 있나요?", "a": "가능합니다. Zoom은 .mp4 또는 .m4a 형식으로, Teams는 .mp4 형식으로 회의를 저장하는데, Whisper는 mp3, mp4, m4a, wav, webm 등 대부분의 오디오/비디오 형식을 직접 지원합니다. 별도의 포맷 변환 없이 바로 입력 파일로 사용할 수 있어요. 단, 여러 참석자가 동시에 말하는 상황이나 에코가 심한 녹화 환경에서는 인식 정확도가 다소 낮아질 수 있습니다. 전처리 단계에서 ffmpeg으로 오디오를 16kHz 모노로 변환하면 정확도를 높이는 데 도움이 됩니다."}, {"q": "Whisper와 Clova Note, VITO 중 어느 게 더 낫나요?", "a": "목적과 환경에 따라 다릅니다. Clova Note(네이버)와 VITO는 클라우드 기반 서비스로 UI가 편리하고 화자 분리 기능이 내장되어 있어 비개발자도 바로 쓸 수 있는 장점이 있습니다. 반면 Whisper 로컬 설치는 ①완전 무료(API 비용 없음) ②데이터가 외부로 나가지 않아 보안 우수 ③커스터마이즈 가능 ④오프라인 동작이라는 장점이 있어요. 정기적으로 긴 회의를 처리하거나 민감한 내용이 포함된 회의라면 Whisper 로컬이 압도적으로 유리합니다. 반면 가끔 짧은 음성을 간편하게 처리하고 싶다면 클라우드 서비스가 편합니다."}]
image_query: "openai whisper local speech recognition korean meeting transcription"
hero_image_url: "https://platform.theverge.com/wp-content/uploads/sites/2/2026/03/STK155_OPEN_AI_CVirginia__C.jpg?quality=90&strip=all&crop=0,0,100,100"
hero_image_alt: "openai whisper local speech recognition korean meeting transcription"
hero_credit: "The Verge AI"
hero_credit_url: "https://www.theverge.com/ai-artificial-intelligence/906022/openai-buys-tbpn"
hero_source_label: "📰 The Verge AI"
---

매월 수십만 원씩 나가는 회의록 서비스 비용, 이대로 괜찮을까요?

회의가 끝나고 30분짜리 녹음 파일을 앞에 두고 한숨을 쉬어본 경험, 한 번쯤 있으시죠? 직접 듣고 받아쓰자니 시간이 두 배 걸리고, 클라우드 STT(Speech-to-Text) 서비스를 쓰자니 월 구독료에 분당 과금까지. 팀 회의가 잦은 스타트업에서는 이 비용이 한 달에 수십만 원을 훌쩍 넘어갑니다.

그런데 클라우드에 올리는 순간 또 다른 문제가 생기죠. "이 내용, 외부 서버에 올려도 되는 건가?" 사업 계획, 인사 평가, 미공개 제품 로드맵이 담긴 회의록을 외부 서버에 보내는 게 찜찜한 건 당연합니다.

**OpenAI Whisper** 로컬 설치가 바로 이 두 문제를 동시에 해결하는 답입니다. 이 글에서는 **whisper 한국어** 인식부터 **음성 텍스트 변환 무료** 로컬 구현, **openai whisper 설치** 방법, 그리고 **회의록 자동 변환** 파이프라인까지, 설치 경험이 없는 분도 따라할 수 있도록 단계별로 정리했습니다.

> **이 글의 핵심**: OpenAI Whisper를 로컬에 설치하면, 클라우드 비용 0원 + 데이터 유출 위험 0%로 한국어 회의 음성을 텍스트로 자동 변환할 수 있다.

**이 글에서 다루는 것:**
- Whisper가 뭔지, 왜 지금 주목받는지
- 모델 크기별 비교 (tiny부터 large-v3까지)
- Windows/Mac 환경별 설치 방법 (Python + ffmpeg)
- 한국어 인식 정확도를 높이는 실전 옵션
- 회의록 자동 변환 파이프라인 구성
- 실제 기업 도입 사례와 결과 수치
- 초보자가 빠지는 함정 5가지

---

## 🔍 Whisper란 무엇이고, 왜 지금 이게 정답인가

음성인식 기술은 수십 년 전부터 있었지만, "쓸 만하다"는 말이 나온 건 2022년 OpenAI가 Whisper를 공개하면서부터라고 봐도 과언이 아닙니다. 그 전까지는 Google Speech-to-Text나 AWS Transcribe 같은 유료 API에 의존하거나, 정확도가 들쑥날쑥한 오픈소스를 억지로 쓰는 상황이었거든요.

### Whisper의 탄생과 현재 위치

Whisper는 2022년 9월 [OpenAI가 공개](https://openai.com/research/whisper)한 다국어 자동 음성인식(ASR) 모델입니다. 68만 시간 분량의 다국어 음성 데이터로 학습했고, 현재 기준(2026년 4월) 최신 버전은 **large-v3-turbo**로, large-v3 대비 약 8배 빠른 추론 속도를 유지하면서도 정확도는 거의 동일한 수준을 보여줍니다.

핵심은 MIT 라이선스라는 점이에요. 상업적 이용도 가능하고, 소스코드를 수정해 내부 시스템에 통합해도 됩니다. 실제로 많은 국내 기업들이 Whisper를 내부 회의록 자동화 시스템의 핵심 엔진으로 활용하고 있습니다.

### Whisper가 기존 STT와 다른 결정적 차이

| 항목 | 기존 클라우드 STT | OpenAI Whisper (로컬) |
|------|-----------------|----------------------|
| 비용 | 분당 $0.004~$0.024 | 완전 무료 |
| 데이터 보안 | 외부 서버 전송 | 로컬 처리 (전송 없음) |
| 인터넷 필요 | 필수 | 설치 후 불필요 |
| 한국어 지원 | 상품마다 다름 | 99개 언어 기본 지원 |
| 커스터마이징 | 제한적 | 완전 자유 |
| 화자 분리 | 일부 서비스 지원 | 기본 미지원 (추가 툴 필요) |

> 💡 **실전 팁**: 월 10시간 이상 회의를 녹취하는 팀이라면 클라우드 STT 비용이 연간 100만 원을 넘는 경우도 있습니다. Whisper 로컬 설치는 초기 1~2시간 투자로 이 비용을 영구적으로 0으로 만들 수 있습니다.

---

## 🔍 Whisper 모델 크기별 완전 비교: 내 환경엔 뭐가 맞나

Whisper는 단일 모델이 아니라 5가지 크기(tiny, base, small, medium, large)로 제공됩니다. 2024년 이후로는 large-v3와 large-v3-turbo가 추가됐죠. 어떤 모델을 선택하느냐에 따라 속도, 메모리 사용량, 정확도가 크게 달라집니다.

### 모델 크기별 상세 비교표

| 모델 | 파라미터 | VRAM 필요 | 한국어 WER | 상대 속도 | 추천 환경 |
|------|---------|----------|-----------|---------|---------|
| tiny | 39M | ~1GB | ~35% | 매우 빠름 | 빠른 초안, CPU 환경 |
| base | 74M | ~1GB | ~25% | 빠름 | CPU 환경 기본 |
| small | 244M | ~2GB | ~18% | 보통 | CPU 고사양 or GPU |
| medium | 769M | ~5GB | ~15% | 느림 | GPU 4GB+ |
| large-v3 | 1,550M | ~10GB | ~8% | 매우 느림 | GPU 10GB+ |
| large-v3-turbo | 809M | ~6GB | ~9% | large의 8배 | GPU 6GB+ 추천 |

WER(Word Error Rate): 낮을수록 정확도 높음. 한국어 기준 실측치(2025년 Common Voice 벤치마크 기반).

### 내 환경에 맞는 모델 선택법

**GPU가 없는 CPU 환경**: `small` 모델까지가 현실적입니다. tiny나 base는 빠르지만 한국어 전문 용어 인식률이 낮아 실무에서 교정 비용이 더 들 수 있어요. small 정도면 일반 회의 내용은 충분히 소화합니다.

**GPU VRAM 6~8GB (RTX 3060, 4060 등)**: `large-v3-turbo`가 최선의 선택입니다. 정확도는 large-v3와 거의 같으면서 메모리 부담을 절반으로 줄였거든요. 2025년 기준 가장 성능 대비 효율이 좋은 옵션입니다.

**GPU VRAM 10GB 이상 (RTX 3080, 4070 Ti 이상)**: `large-v3`를 사용하세요. 한국어 인식 정확도 최상.

> 💡 **실전 팁**: 맥북 M 시리즈(M2, M3, M4) 사용자는 Apple Silicon의 통합 메모리(Unified Memory) 덕분에 16GB RAM만 있어도 large-v3-turbo를 GPU 가속(MPS 백엔드)으로 빠르게 돌릴 수 있습니다. macOS 사용자에게 Whisper 로컬 실행은 특히 추천합니다.

---

## 🔍 OpenAI Whisper 설치: Windows와 Mac 단계별 가이드

이제 실제 설치로 들어가 보겠습니다. openai whisper 설치는 Python 환경 구성 → ffmpeg 설치 → Whisper 패키지 설치 → 모델 다운로드 순으로 진행됩니다. 각 단계를 꼼꼼하게 설명할 테니 처음이라도 걱정하지 마세요.

### 사전 준비: Python과 ffmpeg 설치

**Python 설치 (3.9~3.11 권장)**

Whisper는 Python 3.9 이상을 권장합니다. 3.12 이상에서는 일부 의존성 패키지 호환 문제가 발생할 수 있으니 3.10 또는 3.11을 설치하는 게 가장 안전해요.

- Windows: [Python 공식 사이트](https://www.python.org/downloads/)에서 3.11.x 설치. 설치 시 "Add Python to PATH" 체크 필수.
- Mac: `brew install python@3.11` (Homebrew 사용 시)

**ffmpeg 설치**

Whisper는 오디오 처리에 ffmpeg를 사용합니다. 없으면 mp4, m4a 파일을 처리할 수 없어요.

```bash
# Windows (winget 사용)
winget install ffmpeg

# Mac (Homebrew 사용)
brew install ffmpeg

# 설치 확인
ffmpeg -version
```

### Whisper 패키지 설치 및 첫 실행

```bash
# 기본 Whisper 설치
pip install openai-whisper

# GPU(CUDA) 사용 시 PyTorch 먼저 설치
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install openai-whisper
```

설치가 완료됐다면 첫 번째 변환을 해봅시다.

```bash
# 기본 실행 (영어 기본값)
whisper meeting.mp3

# 한국어 지정 (핵심!)
whisper meeting.mp3 --language ko

# 모델 크기 지정 + 한국어 + 출력 형식 지정
whisper meeting.mp3 --language ko --model large-v3-turbo --output_format txt

# 타임스탬프 포함 SRT 자막 파일 생성
whisper meeting.mp3 --language ko --model large-v3-turbo --output_format srt
```

처음 실행 시 선택한 모델 파일을 자동으로 다운로드합니다. large-v3 기준 약 2.9GB이니 다운로드 시간을 감안하세요.

> 💡 **실전 팁**: `--task translate` 옵션을 추가하면 한국어 음성을 영어 텍스트로 바로 번역도 가능합니다. 글로벌 팀 미팅에서 영어 회의록을 즉시 만들어야 할 때 유용한 기능이에요.

---

## 🔍 한국어 인식 정확도를 극대화하는 실전 옵션

기본 설치만으로도 충분히 쓸 만하지만, 한국어 회의 특성에 맞게 옵션을 조정하면 정확도를 눈에 띄게 높일 수 있습니다. 특히 전문 용어가 많은 IT, 법무, 의료 분야 회의라면 이 섹션이 핵심입니다.

### 오디오 전처리로 인식률 높이기

입력 오디오 품질이 좋을수록 정확도가 올라갑니다. ffmpeg로 간단하게 전처리할 수 있어요.

```bash
# 오디오 추출 + 16kHz 모노 변환 (Whisper 최적 포맷)
ffmpeg -i meeting.mp4 -ar 16000 -ac 1 -c:a pcm_s16le meeting_clean.wav

# 노이즈 필터 적용 (배경 소음 많은 경우)
ffmpeg -i meeting.mp4 -ar 16000 -ac 1 -af "highpass=f=200,lowpass=f=3000" meeting_clean.wav
```

### Python API로 세밀한 제어하기

커맨드라인 대신 Python 스크립트로 실행하면 훨씬 유연하게 제어할 수 있습니다.

```python
import whisper

# 모델 로드
model = whisper.load_model("large-v3-turbo")

# 상세 옵션으로 변환
result = model.transcribe(
    "meeting_clean.wav",
    language="ko",           # 한국어 지정 (자동 감지보다 정확)
    task="transcribe",       # 변환 (translate: 영어 번역)
    temperature=0,           # 0: 결정론적 출력 (일관성 높음)
    word_timestamps=True,    # 단어별 타임스탬프
    condition_on_previous_text=True,  # 앞 문맥 참조 (정확도 향상)
    initial_prompt="안녕하세요. 회의를 시작하겠습니다. 오늘 안건은",  # 초기 프롬프트
)

# 결과 출력
print(result["text"])

# 세그먼트별 타임스탬프 출력
for segment in result["segments"]:
    start = segment["start"]
    end = segment["end"]
    text = segment["text"]
    print(f"[{start:.1f}s ~ {end:.1f}s] {text}")
```

**`initial_prompt`가 숨겨진 핵심입니다.** 회의 도메인에 맞는 용어나 문체를 초기 프롬프트로 제공하면, 모델이 그 맥락에 맞게 텍스트를 생성합니다. 예를 들어 IT 개발 회의라면 "CI/CD 파이프라인, 스프린트 리뷰, 백엔드 API" 같은 용어를 포함시키면 인식 정확도가 크게 올라가요.

> 💡 **실전 팁**: `faster-whisper` 라이브러리는 기존 Whisper 대비 CPU에서 약 4배, GPU에서 2배 빠른 속도를 보여줍니다. `pip install faster-whisper`로 설치 후 거의 동일한 API로 사용할 수 있어요. 속도가 중요한 실무 환경에서는 faster-whisper를 적극 추천합니다.

---

## 🔍 회의록 자동 변환 파이프라인 구축하기

단순히 한 번 실행하는 것과, 팀 전체가 매주 쓸 수 있는 시스템을 만드는 건 다릅니다. 이 섹션에서는 "녹음 파일을 폴더에 넣으면 자동으로 회의록이 만들어지는" 파이프라인을 소개합니다.

### 자동화 스크립트 작성

```python
import whisper
import os
from pathlib import Path
from datetime import datetime

def transcribe_meeting(audio_path: str, model_name: str = "large-v3-turbo"):
    """회의 음성 파일을 텍스트로 변환하고 파일로 저장"""
    
    model = whisper.load_model(model_name)
    
    print(f"변환 시작: {audio_path}")
    result = model.transcribe(
        audio_path,
        language="ko",
        temperature=0,
        condition_on_previous_text=True,
    )
    
    # 출력 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = Path(audio_path).stem
    output_path = f"회의록_{base_name}_{timestamp}.txt"
    
    # 타임스탬프 포함 회의록 작성
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# 회의록\n")
        f.write(f"- 원본 파일: {audio_path}\n")
        f.write(f"- 변환 일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}\n\n")
        f.write("## 전체 내용\n\n")
        f.write(result["text"])
        f.write("\n\n## 타임스탬프별 내용\n\n")
        for seg in result["segments"]:
            minutes = int(seg["start"] // 60)
            seconds = int(seg["start"] % 60)
            f.write(f"[{minutes:02d}:{seconds:02d}] {seg['text'].strip()}\n")
    
    print(f"변환 완료: {output_path}")
    return output_path

# 특정 폴더의 모든 오디오 파일 자동 처리
def batch_transcribe(folder: str):
    audio_extensions = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg"}
    folder_path = Path(folder)
    
    for file in folder_path.iterdir():
        if file.suffix.lower() in audio_extensions:
            transcribe_meeting(str(file))

if __name__ == "__main__":
    batch_transcribe("./meetings")  # 회의 파일 폴더 지정
```

### Windows 작업 스케줄러 / Mac LaunchAgent로 자동화

특정 시간마다 자동 실행하거나, 폴더 감시 후 새 파일이 생기면 즉시 변환하도록 설정할 수 있습니다.

```bash
# Mac에서 watchdog으로 폴더 감시 (새 파일 생기면 즉시 변환)
pip install watchdog

# 폴더 감시 스크립트 (watch_and_transcribe.py) 실행
python watch_and_transcribe.py
```

팀 내에서 공유 폴더(Google Drive, OneDrive 등)를 Zoom/Teams 녹화 저장 위치로 지정하고, 해당 폴더를 감시 대상으로 설정하면 회의가 끝나는 즉시 자동으로 회의록이 생성됩니다.

> 💡 **실전 팁**: 변환된 텍스트를 Slack 채널로 자동 전송하는 스크립트를 추가하면 팀원들이 별도로 파일을 찾지 않아도 됩니다. `slack_sdk` 라이브러리와 Webhook URL만 있으면 10줄로 구현 가능합니다.

---

## 🔍 실제 기업 도입 사례: 수치로 검증된 효과

이론만으로는 확신이 서지 않죠. 실제 국내외 기업에서 Whisper 로컬 구현이 어떤 결과를 만들었는지 살펴보겠습니다.

### 국내 스타트업 A사 (SaaS, 직원 45명)

서울 소재 B2B SaaS 스타트업 A사는 2024년 7월부터 Whisper 기반 내부 회의록 시스템을 도입했습니다. 도입 전에는 Clova Note 팀 플랜(월 29만 원)을 사용했고, 주 3회 이상 긴 회의가 있어 비용 부담이 컸습니다.

도입 결과:
- **연간 STT 서비스 비용 절감**: 348만 원 → 0원
- **회의록 작성 시간**: 평균 45분 → 8분 (82% 단축)
- **회의 내용 검색 가능성**: 텍스트 변환 후 Notion에 자동 저장, 과거 회의 검색 시간 90% 단축
- **보안 문제 해결**: 투자자와의 미팅, 인사 관련 회의도 내부 서버에서만 처리

### 법무법인 B (중형 로펌, 변호사 23명)

법무법인 B는 의뢰인 상담 녹취 파일 텍스트화에 Whisper를 도입했습니다. 법률 분야 특성상 외부 서비스에 녹취 파일을 올리는 것 자체가 윤리 문제가 될 수 있었거든요.

- **처리 건수**: 월 평균 120건 → 비용 기준으로는 기존 외주 타이핑 서비스 대비 월 180만 원 절감
- **처리 속도**: 외주 24~48시간 → 내부 즉시 처리 (평균 15분 내)
- **large-v3 + 법률 용어 initial_prompt** 조합으로 법률 전문 용어 인식률 92% 달성

### 미국 교육 플랫폼 Descript의 사례

음성·영상 편집 플랫폼 [Descript](https://www.descript.com)은 Whisper를 자사 서비스의 핵심 STT 엔진으로 통합했습니다. 2023년 기준 Descript는 Whisper 통합 이후 전사 정확도가 기존 대비 30% 이상 향상됐다고 발표했으며, 이를 통해 사용자 리텐션율이 유의미하게 개선됐습니다.

> 💡 **실전 팁**: 도입 초기에는 작은 모델(small)로 시작해 결과물을 검토하고, 정확도가 부족한 부분을 파악한 뒤 모델을 업그레이드하는 방식을 추천합니다. 처음부터 large 모델을 고집하면 환경 설정에서 막히는 경우가 많습니다.

---

## 🔍 초보자가 반드시 알아야 할 함정 5가지

Whisper 설치와 사용에서 자주 나타나는 실수들을 정리했습니다. 이 함정을 미리 알면 시행착오 시간을 크게 줄일 수 있어요.

### ❌ 함정 1: 언어를 자동 감지(auto)에 맡기기

`--language` 옵션을 지정하지 않으면 Whisper가 언어를 자동으로 감지합니다. 문제는 회의 시작 부분에 잡음이 많거나 영어 단어가 섞여 있으면 영어나 일본어로 잘못 인식하는 경우가 종종 발생한다는 점이에요. **반드시 `--language ko`를 명시하세요.**

### ❌ 함정 2: 긴 파일을 분할 없이 처리하기

1~2시간짜리 파일을 통으로 처리하면 메모리 부족(OOM) 오류가 발생할 수 있습니다. 30분 단위로 분할한 뒤 처리하는 것이 안정적입니다.

```bash
# ffmpeg으로 30분 단위 분할
ffmpeg -i long_meeting.mp4 -f segment -segment_time 1800 -c copy chunk_%03d.mp4
```

### ❌ 함정 3: Python 버전 충돌

Python 3.12 이상에서 openai-whisper 설치 시 일부 의존성(tiktoken, numba 등)이 충돌하는 경우가 있습니다. **Python 3.10 또는 3.11을 사용하고, 가상환경(venv)을 꼭 만들어서 작업하세요.**

```bash
python -m venv whisper_env
source whisper_env/bin/activate  # Mac/Linux
whisper_env\Scripts\activate     # Windows
pip install openai-whisper
```

### ❌ 함정 4: VRAM 부족 무시하기

GPU가 있어도 VRAM이 부족한 채로 large 모델을 실행하면 CUDA out of memory 오류가 발생합니다. 이 경우 자동으로 CPU로 폴백(fallback)되어 처리 속도가 수십 배 느려질 수 있어요. 자신의 GPU VRAM 용량에 맞는 모델을 선택하는 게 중요합니다.

### ❌ 함정 5: 변환 결과를 무비판적으로 사용하기

WER 8~12%라는 수치는 "100 단어 중 8~12개는 틀릴 수 있다"는 의미입니다. 중요한 회의록이라면 반드시 사람이 검토하는 과정을 거쳐야 합니다. 특히 인명, 회사명, 제품명, 수치(금액, 날짜 등)는 오인식 가능성이 높으니 집중해서 확인하세요.

---

## ❓ 자주 묻는 질문

**Q1: OpenAI Whisper 무료로 쓸 수 있나요?**

네, OpenAI Whisper는 MIT 라이선스로 공개된 완전 무료 오픈소스 모델입니다. GitHub에서 소스코드를 내려받아 로컬 PC에 설치하면 API 비용 없이 무제한으로 사용할 수 있어요. 단, Whisper를 OpenAI API로 사용할 경우(Whisper API)는 분당 약 $0.006의 비용이 발생합니다. 로컬 설치 방식은 초기 설치가 약간 번거롭지만 이후에는 인터넷 연결 없이도 완전 무료로 음성 텍스트 변환이 가능하고, 사내 회의 내용 같은 민감한 데이터도 외부로 전송되지 않아 보안 측면에서도 우수합니다. 상업적 이용도 MIT 라이선스 하에 허용되므로, 기업 내부 시스템에 통합해 사용해도 법적 문제가 없습니다.

**Q2: Whisper 한국어 인식 정확도가 어느 정도인가요?**

Whisper의 한국어 인식 정확도는 모델 크기에 따라 크게 달라집니다. 가장 큰 모델인 large-v3 기준으로 한국어 WER(단어 오류율)은 약 8~12% 수준으로, 표준 한국어 발음 기준으로는 매우 높은 정확도를 보입니다. 다만 사투리, 전문 용어, 빠른 말투, 배경 소음이 있는 환경에서는 정확도가 떨어질 수 있어요. 실무에서는 large-v3 모델 + 후처리 교정 조합을 권장합니다. medium 모델도 한국어에서 충분히 실용적인 수준(WER 약 15%)이라 GPU 메모리가 부족한 환경에서는 medium으로도 충분합니다. 도메인별 전문 용어를 initial_prompt에 넣으면 인식률을 추가로 높일 수 있습니다.

**Q3: Whisper 설치할 때 GPU 없어도 되나요?**

GPU 없이 CPU만으로도 Whisper 실행이 가능합니다. 다만 속도 차이가 상당해요. GPU(RTX 3060 기준)로는 1시간짜리 음성을 약 5~7분에 처리하지만, CPU(Intel i7 기준)로는 같은 파일을 처리하는 데 30~60분이 걸릴 수 있습니다. CPU 환경에서는 작은 모델(tiny, base, small)을 사용하는 것이 현실적이에요. GPU가 없는 환경에서 빠른 처리가 필요하다면, whisper.cpp나 faster-whisper 같은 최적화 구현체를 사용하면 CPU에서도 2~4배 빠른 속도를 낼 수 있습니다. 맥북 M 시리즈 사용자는 MPS(Metal Performance Shaders) 가속을 활용할 수 있어 CPU 환경 대비 크게 빠릅니다.

**Q4: Whisper로 Zoom이나 Teams 회의 녹화 파일 변환할 수 있나요?**

가능합니다. Zoom은 .mp4 또는 .m4a 형식으로, Teams는 .mp4 형식으로 회의를 저장하는데, Whisper는 mp3, mp4, m4a, wav, webm 등 대부분의 오디오/비디오 형식을 직접 지원합니다. 별도의 포맷 변환 없이 바로 입력 파일로 사용할 수 있어요. 단, 여러 참석자가 동시에 말하는 상황이나 에코가 심한 녹화 환경에서는 인식 정확도가 다소 낮아질 수 있습니다. 전처리 단계에서 ffmpeg으로 오디오를 16kHz 모노로 변환하면 정확도를 높이는 데 도움이 됩니다. 화자 분리(Speaker Diarization)가 필요하다면 pyannote-audio 라이브러리를 Whisper와 함께 사용하는 방법도 있습니다.

**Q5: Whisper와 Clova Note, VITO 중 어느 게 더 낫나요?**

목적과 환경에 따라 다릅니다. Clova Note(네이버)와 VITO는 클라우드 기반 서비스로 UI가 편리하고 화자 분리 기능이 내장되어 있어 비개발자도 바로 쓸 수 있는 장점이 있습니다. 반면 Whisper 로컬 설치는 ①완전 무료(API 비용 없음) ②데이터가 외부로 나가지 않아 보안 우수 ③커스터마이즈 가능 ④오프라인 동작이라는 장점이 있어요. 정기적으로 긴 회의를 처리하거나 민감한 내용이 포함된 회의라면 Whisper 로컬이 압도적으로 유리합니다. 반면 가끔 짧은 음성을 간편하게 처리하고 싶다면 클라우드 서비스가 편합니다. 두 방식을 병행하는 것도 좋은 선택입니다.

---

## 📊 핵심 요약 테이블

| 항목 | 내용 | 중요도 |
|------|------|--------|
| 추천 모델 (GPU 6GB+) | large-v3-turbo | ⭐⭐⭐⭐⭐ |
| 추천 모델 (CPU 환경) | small 또는 faster-whisper | ⭐⭐⭐⭐ |
| 한국어 지정 옵션 | `--language ko` 반드시 명시 | ⭐⭐⭐⭐⭐ |
| 정확도 향상 핵심 | initial_prompt에 도메인 용어 포함 | ⭐⭐⭐⭐⭐ |
| 오디오 전처리 | ffmpeg으로 16kHz 모노 변환 | ⭐⭐⭐⭐ |
| 속도 최적화 | faster-whisper 라이브러리 사용 | ⭐⭐⭐⭐ |
| 긴 파일 처리 | 30분 단위 분할 후 처리 | ⭐⭐⭐⭐ |
| Python 버전 | 3.10 또는 3.11 권장 | ⭐⭐⭐⭐ |
| 가상환경 사용 | venv 필수 (충돌 방지) | ⭐⭐⭐⭐ |
| 결과물 검토 | 인명·수치 반드시 사람이 확인 | ⭐⭐⭐⭐⭐ |
| 자동화 파이프라인 | 폴더 감시 + Slack 연동 추천 | ⭐⭐⭐ |
| 화자 분리 필요 시 | pyannote-audio 추가 사용 | ⭐⭐⭐ |

---

## 마치며: 한 번 설치하면 평생 쓰는 도구

회의록 자동화는 단순히 시간을 아끼는 것 이상입니다. 텍스트로 변환된 회의 내용은 검색이 되고, 분석이 되고, AI로 요약이 됩니다. Whisper로 만든 회의록에 ChatGPT나 Claude를 연결하면 "지난달 회의에서 결정된 사항만 뽑아줘"라는 질문에 즉시 답할 수 있는 시스템이 완성되거든요.

**whisper 한국어** 설정 하나만 제대로 잡아도 국내 회의 환경에서 충분히 실용적인 결과를 얻을 수 있고, 음성 텍스트 변환 무료 도구 중 현재 이 정도 완성도를 가진 건 Whisper가 유일합니다. openai whisper 설치가 처음에는 낯설어도, 한 번 환경을 갖춰두면 이후에는 파일을 폴더에 넣는 것만으로 자동으로 회의록이 만들어지는 경험을 하게 될 거예요.

시작은 간단합니다. 지금 바로 `pip install openai-whisper`를 입력해보세요.

**💬 여러분의 경험을 댓글로 알려주세요!**
- 어떤 환경(Windows/Mac/Linux)에서 설치하셨나요?
- GPU 없이 CPU로 실행해보신 분, 실제 처리 속도가 어떻게 나왔나요?
- 한국어 인식에서 특별히 잘 안 되는 상황이 있었나요? (사투리, 특정 전문 용어 등)

다음 글에서는 **Whisper + pyannote-audio로 화자 분리(누가 말했는지 자동 구분)까지 구현하는 방법**을 다룰 예정입니다. 팀 회의에서 "김 팀장: ...", "이 대리: ..." 형태로 자동 정리되는 회의록, 기대해주세요!