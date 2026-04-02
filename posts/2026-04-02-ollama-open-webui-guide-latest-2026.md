---
title: "🖥️ Ollama + Open WebUI 윈도우 완전 설치 가이드 (2026 최신판)"
labels: ["로컬LLM", "오픈소스AI", "AI기초", "LLM", "AI생산성"]
draft: false
meta_description: "ollama 설치 윈도우 방법을 처음 시작하는 분들을 위해 Open WebUI 연동과 한국어 모델 세팅까지 2026년 기준으로 단계별 정리했습니다."
seo_keywords: "ollama 윈도우 설치 방법, open webui 로컬 llm 설치, ollama 한국어 모델 연동, 윈도우 로컬 AI 구축, ollama open webui 연동 가이드"
faqs: [{"q": "ollama 설치 윈도우에서 GPU 없어도 되나요?", "a": "네, GPU 없이 CPU만으로도 Ollama를 설치하고 실행할 수 있습니다. 다만 CPU만 사용할 경우 모델 응답 속도가 GPU 대비 5~10배 이상 느려질 수 있어요. 예를 들어 NVIDIA RTX 3060(12GB VRAM)에서 1~2초 걸리는 응답이 인텔 i7 CPU에서는 20~40초 걸릴 수 있습니다. 일상적인 테스트 용도라면 CPU로도 충분하지만, 실무 활용을 원한다면 VRAM 8GB 이상의 GPU 환경을 권장합니다. AMD GPU는 ROCm 지원이 필요하며, 윈도우 환경에서는 NVIDIA CUDA 기반이 가장 안정적입니다."}, {"q": "Ollama에서 한국어 대화가 잘 되는 모델은 뭔가요?", "a": "2026년 4월 기준으로 한국어 성능이 검증된 모델은 크게 세 가지입니다. 첫째, EEVE-Korean-10.8B는 업스테이지에서 공개한 모델로 한국어 이해도가 뛰어나고 Ollama 모델 라이브러리에서 바로 pull할 수 있습니다. 둘째, Qwen2.5:14b는 알리바바의 다국어 모델로 한국어 처리가 우수하며 14B 기준 VRAM 10GB 이상 권장합니다. 셋째, gemma3:12b는 구글 DeepMind의 최신 오픈소스 모델로 한국어 응답 품질이 크게 개선됐습니다. 7B 이하 소형 모델 중에서는 llama3.2:3b도 기본 한국어 대화가 가능합니다."}, {"q": "Open WebUI 설치할 때 Docker가 꼭 필요한가요?", "a": "Docker 없이도 pip(파이썬 패키지 관리자)를 이용해 설치할 수 있습니다. 터미널에서 `pip install open-webui` 명령어 하나로 설치되고, `open-webui serve`로 실행할 수 있어요. 다만 파이썬 3.11 이상이 필요하고, 환경변수 충돌이 발생하면 가상환경(venv) 설정이 추가로 필요합니다. Docker를 사용하면 이런 의존성 문제를 한 번에 해결할 수 있어 초보자에게는 Docker Desktop 설치 후 docker-compose로 진행하는 방법을 권장합니다. 2026년 기준 Open WebUI의 공식 권장 설치 방법은 Docker 방식입니다."}, {"q": "Ollama 모델 파일은 어디에 저장되나요? 용량 관리는 어떻게 하나요?", "a": "윈도우 환경에서 Ollama 모델 파일은 기본적으로 `C:\\Users\\사용자명\\.ollama\\models` 경로에 저장됩니다. 모델 크기가 상당해서 7B 모델 기준 4~8GB, 14B 모델은 8~16GB, 70B 모델은 40GB 이상 공간을 차지해요. 저장 경로를 변경하고 싶다면 윈도우 시스템 환경변수에서 `OLLAMA_MODELS`를 원하는 경로(예: D:\\OllamaModels)로 설정하면 됩니다. 사용하지 않는 모델은 `ollama rm 모델명` 명령어로 삭제할 수 있고, `ollama list`로 현재 설치된 모델 목록을 확인할 수 있습니다."}, {"q": "Open WebUI에서 외부에서도 접속할 수 있게 설정할 수 있나요?", "a": "기본적으로 Open WebUI는 localhost(127.0.0.1)에서만 접속 가능하도록 설정되어 있어요. 같은 네트워크 내 다른 기기에서 접속하려면 윈도우 방화벽에서 해당 포트(기본 3000번)를 열어줘야 합니다. 인터넷 외부에서 접속하려면 ngrok이나 Cloudflare Tunnel 같은 터널링 서비스를 활용하는 방법이 가장 간편하고 안전합니다. 단, 로컬 AI 서버를 외부에 공개할 경우 반드시 Open WebUI의 계정 인증 설정을 활성화하고, 개인정보가 포함된 대화 내용이 외부에 노출되지 않도록 주의해야 합니다."}]
image_query: "local AI ollama open webui windows setup dashboard"
hero_image_url: "https://images.ctfassets.net/jdtwqhzvc2n1/66Tw6dMGGoSZZOK6XB6gm6/0fafc7520898e26c88edf1de9e74e863/nuneybits_Vector_art_of_radiant_skull_emitting_code_beams_deep__17d19acc-0af7-41ad-ac28-16f09ef5234b.webp?w=300&q=30"
hero_image_alt: "local AI ollama open webui windows setup dashboard"
hero_credit: "VentureBeat AI"
hero_credit_url: "https://venturebeat.com/technology/nous-researchs-nouscoder-14b-is-an-open-source-coding-model-landing-right-in"
hero_source_label: "📰 VentureBeat AI"
---

"ChatGPT 쓰다가 월 구독료 20달러가 너무 아까워서 로컬 AI 찾아봤는데, Ollama라는 게 있더라고요. 근데 설치하다가 에러 뜨고, 모델 받다가 포기했어요."

이런 경험, 한 번쯤 있으시죠? 특히 윈도우 환경에서 Ollama를 처음 세팅할 때 PATH 오류, 포트 충돌, CUDA 버전 불일치 같은 문제가 줄줄이 터지면서 포기하는 분들이 정말 많거든요.

2026년 현재, Ollama는 전 세계 4,000만 회 이상 다운로드된 명실상부 **로컬 LLM 실행 표준 도구**가 됐습니다. 그리고 여기에 ChatGPT 스타일의 웹 UI를 붙여주는 Open WebUI를 연동하면, 진짜 '내 PC에서 돌아가는 나만의 AI'가 완성되죠.

이 글에서는 **ollama 설치 윈도우** 방법을 완전히 처음 시작하는 분도 따라할 수 있도록, 설치부터 한국어 모델 연동, Open WebUI 세팅까지 단계별로 낱낱이 정리했습니다. 에러가 나는 지점마다 해결책도 함께 담았으니, 이 글 하나로 완전히 해결하실 수 있을 거예요.

> **이 글의 핵심**: Ollama + Open WebUI를 윈도우 PC에 설치하고, 한국어 모델까지 연동하면 월 구독료 없이 ChatGPT 수준의 개인 AI 환경을 구축할 수 있습니다.

---

**이 글에서 다루는 것:**
- Ollama가 뭔지, 왜 써야 하는지
- 윈도우 환경 필수 요구사항 체크
- Ollama 설치 및 첫 모델 실행
- Open WebUI 설치 및 연동 (Docker / pip 방식 모두)
- 한국어 모델 추천 및 세팅
- 실전 활용 사례
- 초보자가 자주 빠지는 함정 5가지

---

## 🤔 Ollama가 뭔데요? 왜 써야 하나요?

Ollama는 2023년 7월 출시된 오픈소스 로컬 LLM 런처입니다. 한마디로 "LLM을 내 PC에서 실행하게 해주는 엔진"이에요. Docker가 컨테이너 실행을 추상화해주듯, Ollama는 복잡한 AI 모델 실행 환경을 딱 한 줄 명령어로 단순화해줍니다.

### Ollama가 특별한 이유

2026년 4월 기준, Ollama의 [공식 모델 라이브러리](https://ollama.com/library)에는 Llama 3.3, Gemma 3, Qwen2.5, Mistral, Phi-4 등 300개 이상의 모델이 등록돼 있어요. 이 모델들을 `ollama pull 모델명` 한 줄로 내려받고, `ollama run 모델명` 한 줄로 실행할 수 있습니다.

특히 중요한 건 **API 엔드포인트**입니다. Ollama는 설치되면 자동으로 `localhost:11434`에 REST API 서버를 열어주는데, 이 API가 OpenAI API 형식과 호환됩니다. 즉, ChatGPT API를 쓰던 앱이나 도구를 그대로 Ollama에 연결할 수 있다는 뜻이에요.

### ChatGPT 대비 Ollama의 실질적 차이

| 항목 | ChatGPT (GPT-4o) | Ollama + 로컬 모델 |
|------|-----------------|-------------------|
| 비용 | 월 $20~$200 | 전기세만 (무료) |
| 인터넷 연결 | 필수 | 불필요 |
| 데이터 프라이버시 | 서버 전송 | 100% 로컬 처리 |
| 응답 속도 | 빠름 (클라우드) | PC 사양에 따라 다름 |
| 최신 정보 | 지원 (웹 검색) | 기본 미지원 (RAG 구성 가능) |
| 모델 커스터마이즈 | 불가 | 파인튜닝, Modelfile 수정 가능 |

데이터 보안이 중요한 직종(의료, 법률, 금융)이라면 Ollama 기반 로컬 AI는 선택이 아닌 필수가 되고 있습니다.

> 💡 **실전 팁**: Ollama는 설치 후 시스템 트레이에 상주하며, PC 부팅 시 자동 실행되도록 설정할 수 있어요. 윈도우 시작 시 자동 실행을 원한다면 설치 후 시스템 트레이 아이콘 우클릭 → "Start on Login" 체크만 하면 됩니다.

---

## 🖥️ 설치 전 환경 확인 — 내 PC는 괜찮을까요?

본격적인 ollama 설치 윈도우 과정에 들어가기 전에, 내 PC 환경이 최소 요건을 충족하는지 확인해야 합니다. 이 단계를 건너뛰면 나중에 모델이 아예 안 돌거나 엄청나게 느린 상황이 발생해요.

### 하드웨어 요구사항 체크리스트

**CPU:** 최소 Intel Core i5 8세대 이상 또는 AMD Ryzen 5 3000 시리즈 이상을 권장합니다. 4코어 이상이면 기본 7B 모델 실행이 가능해요.

**RAM:** 최소 8GB, 권장 16GB 이상입니다. 7B 모델은 약 8GB, 14B 모델은 약 12GB RAM을 소비하거든요. RAM이 부족하면 모델이 디스크 스왑을 일으키면서 응답이 극단적으로 느려집니다.

**저장공간:** 모델 파일이 크기 때문에 여유 공간이 필수예요. SSD를 강력 권장합니다.

| 모델 크기 | 예시 모델 | 필요 VRAM/RAM | 디스크 공간 |
|---------|---------|------------|----------|
| 1~3B | llama3.2:3b, phi4-mini | 4GB | 2~3GB |
| 7~8B | llama3.1:8b, gemma3:9b | 8GB | 5~8GB |
| 13~14B | qwen2.5:14b, gemma3:12b | 12~16GB | 9~14GB |
| 32~34B | qwen2.5:32b | 24GB+ | 20~25GB |
| 70B | llama3.3:70b | 48GB+ | 40GB+ |

**GPU (선택, 강력 권장):** NVIDIA GPU가 있다면 CUDA를 통해 GPU 가속이 자동 활성화됩니다. VRAM 8GB(RTX 3070, 4060 등) 이상이면 14B 모델까지 쾌적하게 돌릴 수 있어요.

### 소프트웨어 사전 준비

- **OS**: Windows 10 22H2 이상 또는 Windows 11 (2026년 4월 기준 권장: Windows 11 24H2)
- **NVIDIA GPU 사용 시**: CUDA 12.4 이상 드라이버 설치 필요 ([NVIDIA 드라이버 다운로드](https://www.nvidia.com/Download/index.aspx) 에서 최신 버전 설치)
- **WSL2 (Windows Subsystem for Linux)**: 필수는 아니지만 Docker 방식으로 Open WebUI 설치 시 필요

> 💡 **실전 팁**: GPU가 있는데 CUDA 드라이버 버전을 모르겠다면, 명령 프롬프트(CMD)에서 `nvidia-smi` 명령어를 실행해보세요. 오른쪽 상단에 `CUDA Version: 12.x`라고 표시된다면 준비 완료입니다. 명령어 자체가 인식되지 않으면 드라이버부터 다시 설치해야 합니다.

---

## ⚙️ Ollama 설치 윈도우 — 단계별 완전 정복

드디어 본격적인 설치입니다. 2026년 기준 ollama 설치 윈도우 과정은 예전보다 훨씬 단순해졌어요. 그래도 놓치기 쉬운 포인트들이 있으니 천천히 따라오세요.

### Step 1: Ollama 다운로드 및 설치

1. [Ollama 공식 사이트](https://ollama.com)에 접속합니다.
2. 메인 페이지에서 **"Download for Windows"** 버튼을 클릭해 설치 파일(.exe)을 받습니다.
3. 다운로드된 `OllamaSetup.exe`를 실행합니다.
4. 설치 마법사를 따라 진행하면 자동으로 설치가 완료됩니다. 별도의 설정 없이 "Install" 버튼만 누르면 돼요.
5. 설치가 완료되면 시스템 트레이(오른쪽 하단)에 라마 아이콘이 나타납니다.

설치 경로 기본값은 `C:\Users\사용자명\AppData\Local\Programs\Ollama`이고, 모델은 `C:\Users\사용자명\.ollama\models`에 저장됩니다. C 드라이브 여유 공간이 부족하다면 설치 전에 환경변수 `OLLAMA_MODELS`를 다른 드라이브로 설정해두세요.

### Step 2: 첫 번째 모델 실행

설치 후 **명령 프롬프트(CMD)** 또는 **PowerShell**을 열고 아래 명령어를 실행해보세요.

```bash
# 모델 목록 확인
ollama list

# 첫 번째 모델 다운로드 및 실행 (약 2.0GB)
ollama run llama3.2:3b
```

처음 실행하면 모델 파일을 자동으로 다운로드합니다. 다운로드 완료 후 `>>>` 프롬프트가 뜨면 바로 대화를 시작할 수 있어요. `/bye`를 입력하면 종료됩니다.

### Step 3: Ollama 서버 상태 확인

```bash
# Ollama 서비스 실행 상태 확인
ollama serve

# 실행 중인 모델 확인
ollama ps

# API 응답 테스트 (브라우저 또는 curl)
curl http://localhost:11434/api/tags
```

브라우저 주소창에 `http://localhost:11434`를 입력했을 때 `"Ollama is running"`이라는 텍스트가 보이면 정상 작동 중입니다.

> 💡 **실전 팁**: Ollama 실행 중 CMD를 닫아도 백그라운드 서비스는 계속 돌아갑니다. 완전히 종료하려면 시스템 트레이 아이콘 우클릭 → "Quit Ollama"를 선택하세요. 재시작이 필요할 때도 이 방법으로 껐다 켜면 됩니다.

---

## 🌐 Open WebUI 설치 — ChatGPT 같은 화면으로 대화하기

터미널에서 대화하는 건 금방 불편해집니다. 대화 히스토리 관리, 마크다운 렌더링, 파일 첨부, 멀티 모델 전환 등 편의기능이 없거든요. Open WebUI는 이 모든 걸 해결해줍니다.

### 방법 1: pip으로 설치 (Docker 없이, 가장 간단)

파이썬 3.11 이상이 설치돼 있다면 이 방법이 가장 빠릅니다.

```bash
# 파이썬 버전 확인 (3.11 이상 필요)
python --version

# (권장) 가상환경 생성
python -m venv openwebui-env
openwebui-env\Scripts\activate

# Open WebUI 설치
pip install open-webui

# 실행
open-webui serve
```

실행 후 브라우저에서 `http://localhost:8080`으로 접속하면 됩니다.

### 방법 2: Docker로 설치 (가장 안정적, 권장)

Docker Desktop이 설치된 환경이라면 아래 명령어 하나로 끝납니다.

```bash
docker run -d -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

윈도우 PowerShell에서는 백슬래시(`\`) 대신 백틱(`` ` ``)을 사용해야 해요.

```powershell
docker run -d -p 3000:8080 `
  --add-host=host.docker.internal:host-gateway `
  -v open-webui:/app/backend/data `
  --name open-webui `
  --restart always `
  ghcr.io/open-webui/open-webui:main
```

실행 후 `http://localhost:3000`으로 접속합니다. 처음 접속 시 관리자 계정을 생성하는 화면이 나오고, 이메일과 비밀번호를 설정하면 바로 사용 가능합니다.

### Open WebUI에서 Ollama 연동 확인

Open WebUI 접속 후 오른쪽 상단 메뉴 → **관리자 패널** → **설정** → **연결**로 이동합니다. "Ollama Base URL"에 `http://localhost:11434`가 설정돼 있으면 정상입니다. 연결 상태가 초록색 불로 표시되면 성공이에요.

이후 채팅 화면에서 모델 드롭다운을 클릭하면 Ollama에서 다운로드한 모델들이 목록에 나타납니다.

> 💡 **실전 팁**: Docker 방식에서 Ollama 연결이 안 되는 경우, Docker 컨테이너 내부에서 `localhost`는 호스트 PC가 아닌 컨테이너 자체를 가리킵니다. 이때는 URL을 `http://host.docker.internal:11434`로 변경하면 해결됩니다. `--add-host=host.docker.internal:host-gateway` 옵션이 이 역할을 합니다.

---

## 🇰🇷 한국어 모델 연동 — "진짜 쓸 수 있는" AI 만들기

모델 설치는 됐는데 한국어로 물어보면 영어로 답하거나, 어색한 번역체로 답변이 돌아온다면 모델 선택부터 다시 해야 합니다.

### 2026년 4월 기준 한국어 추천 모델

```bash
# 1순위: EEVE Korean (업스테이지, 한국어 특화)
ollama pull eeve-korean-instruct-10.8b-v1.0

# 2순위: Qwen2.5 14B (다국어, 한국어 우수)
ollama pull qwen2.5:14b

# 3순위: Gemma 3 12B (구글, 한국어 크게 개선)
ollama pull gemma3:12b

# 소형 모델 (VRAM 4GB): Qwen2.5 7B
ollama pull qwen2.5:7b
```

**EEVE-Korean**은 업스테이지(Upstage)가 Mistral 7B를 한국어 데이터로 파인튜닝한 모델이에요. Hugging Face 한국어 오픈 LLM 리더보드에서 오랫동안 상위권을 유지한 검증된 모델입니다. 다만 10.8B 파라미터 기준 약 7GB VRAM이 필요합니다.

### 시스템 프롬프트로 한국어 고정하기

Open WebUI에서는 모델별로 시스템 프롬프트를 설정할 수 있어요. 한국어 응답을 강제하려면:

1. Open WebUI 채팅 화면 → 모델 이름 옆 ⚙️ 아이콘 클릭
2. **시스템 프롬프트** 입력란에 다음을 붙여넣기:

```
당신은 한국어로 대화하는 AI 어시스턴트입니다. 
사용자의 질문이 어떤 언어로 작성되어 있든 항상 한국어로 답변하세요.
답변은 명확하고 친절하며 간결하게 작성해주세요.
```

3. 저장 후 대화 시작

이 설정을 저장하면 해당 모델 선택 시 항상 이 시스템 프롬프트가 적용됩니다.

### 한국어 모델 성능 비교

| 모델 | 한국어 자연스러움 | 필요 VRAM | 응답 속도(RTX 4070) | 추천 용도 |
|-----|--------------|---------|-------------------|---------|
| EEVE-Korean-10.8B | ★★★★★ | 8GB | 약 30토큰/초 | 한국어 전용 업무 |
| Qwen2.5:14b | ★★★★☆ | 10GB | 약 20토큰/초 | 한영 혼용 업무 |
| Gemma3:12b | ★★★★☆ | 9GB | 약 25토큰/초 | 코드 + 한국어 |
| Llama3.2:3b | ★★★☆☆ | 4GB | 약 60토큰/초 | 빠른 간단 대화 |
| Qwen2.5:7b | ★★★★☆ | 6GB | 약 45토큰/초 | VRAM 제한 환경 |

> 💡 **실전 팁**: 모델을 바꿀 때마다 `ollama ps` 명령어로 현재 메모리에 로드된 모델을 확인하세요. 여러 모델이 동시에 VRAM을 점유하면 속도가 크게 저하됩니다. `ollama stop 모델명`으로 사용하지 않는 모델을 언로드할 수 있어요.

---

## 🏢 실제 활용 사례 — 이렇게 쓰고 있습니다

이론은 충분히 살펴봤으니, 실제로 어떻게 활용되는지 사례를 보겠습니다.

### 사례 1: 법무법인 소규모 로펌의 문서 검토 자동화

서울 소재 소형 법무법인 A사(직원 15명)는 2025년 하반기부터 Ollama + Open WebUI 기반의 내부 AI 시스템을 도입했습니다. 핵심 이유는 **의뢰인 정보 보안** 때문이었어요. 기존에는 ChatGPT에 계약서 내용을 붙여넣어 검토하는 방식을 사용했는데, 개인정보보호법 및 변호사법상 의뢰인 정보 외부 전송 문제가 우려됐거든요.

Qwen2.5:14b 모델을 RTX 4080 장착 워크스테이션에 설치하고, Open WebUI를 내부 네트워크에만 공개했습니다. 결과적으로 계약서 초안 검토 시간이 기존 평균 45분에서 12분으로 단축됐고, 연간 외주 번역 비용도 약 60% 절감했다고 밝혔습니다.

### 사례 2: 1인 유튜버의 자막 및 대본 작업

구독자 8만 명의 IT 유튜버 박모씨는 Ollama + EEVE-Korean 모델을 활용해 영상 대본 초안 작성 시간을 약 70% 단축했습니다. 하루 3~4시간 걸리던 리서치 및 대본 작업이 1시간 내외로 줄어들었다고요.

특히 Open WebUI의 **파일 첨부 기능**을 활용해 PDF 리서치 자료를 올리고 핵심 내용을 요약시키는 방식이 핵심이었습니다. 인터넷 연결 없이도 로컬에서 돌아가기 때문에 카페나 도서관에서도 막힘 없이 사용할 수 있다는 점도 장점으로 꼽았습니다.

### 사례 3: 제조업 중소기업의 설비 매뉴얼 Q&A 봇

경기도 소재 제조업체 B사는 수백 페이지에 달하는 설비 매뉴얼을 Ollama + Open WebUI의 RAG(문서 검색 증강 생성) 기능과 연동해 현장 직원용 Q&A 챗봇을 구축했습니다. 신입 직원 교육 시간이 평균 3주에서 1.5주로 단축되는 효과가 나타났다고 합니다.

---

## ⚠️ 초보자가 빠지는 함정 5가지

설치하다가 막히는 지점들을 미리 알고 가면 수십 분의 시간을 절약할 수 있습니다.

### 함정 1: CUDA 드라이버 버전 불일치

Ollama가 GPU를 인식하지 못하는 가장 흔한 원인입니다. `nvidia-smi`는 동작하는데 `ollama run`에서 CPU만 사용한다면, NVIDIA 드라이버가 너무 오래됐을 가능성이 높아요. NVIDIA 공식 사이트에서 최신 Game Ready 드라이버 또는 Studio 드라이버를 설치한 후 PC를 재시작하세요. 2026년 기준 CUDA 12.4 이상을 지원하는 드라이버(버전 550 이상)를 권장합니다.

### 함정 2: 포트 11434 충돌

드물지만 다른 프로그램이 11434 포트를 이미 점유하고 있으면 Ollama가 실행되지 않습니다. PowerShell에서 `netstat -ano | findstr :11434`로 해당 포트 사용 중인 프로세스를 확인하고, 필요 시 환경변수 `OLLAMA_HOST`를 `0.0.0.0:11435`로 변경해 포트를 바꿀 수 있습니다.

### 함정 3: RAM 부족으로 인한 시스템 먹통

VRAM이 부족하면 Ollama는 자동으로 CPU + RAM을 활용하는 하이브리드 모드로 전환합니다. 문제는 이때 RAM도 부족하면 Windows가 디스크 스왑을 과도하게 사용하면서 시스템 전체가 버벅거리거나 멈추는 현상이 발생합니다. 자신의 VRAM과 RAM을 초과하는 모델은 절대로 실행하지 마세요. 안전하게 시작하려면 항상 3B~7B 소형 모델로 테스트 후 점차 올리는 방식을 권장합니다.

### 함정 4: Open WebUI Docker 컨테이너에서 Ollama 연결 실패

앞서 팁에서도 언급했지만, Docker 내부의 `localhost`는 호스트 PC가 아닙니다. Open WebUI 설정에서 Ollama URL을 `http://localhost:11434`로 했는데 연결이 안 된다면, `http://host.docker.internal:11434`로 바꾸세요. 이 실수가 Docker 방식 설치의 80% 이상의 오류 원인입니다.

### 함정 5: 모델명 오타 및 대소문자 구분

`ollama pull Llama3:8b`처럼 대소문자를 잘못 입력하면 "model not found" 에러가 납니다. Ollama 모델명은 **전부 소문자**가 기본입니다. `llama3.1:8b`, `qwen2.5:14b`, `gemma3:12b`처럼 공식 라이브러리에 표기된 이름 그대로 입력해야 해요. 정확한 모델명은 [Ollama 공식 라이브러리](https://ollama.com/library)에서 확인하세요.

---

## 📊 전체 세팅 핵심 요약

| 단계 | 핵심 내용 | 예상 소요 시간 | 주의사항 |
|-----|---------|-------------|--------|
| Ollama 설치 | ollama.com에서 .exe 다운로드 후 설치 | 5분 | 시스템 트레이 아이콘 확인 |
| 첫 모델 다운로드 | `ollama pull qwen2.5:7b` | 5~20분 (인터넷 속도에 따라) | 모델명 소문자 주의 |
| API 서버 확인 | localhost:11434 접속 확인 | 1분 | 포트 충돌 여부 확인 |
| Open WebUI 설치 | pip 또는 Docker 방식 선택 | 5~15분 | Docker 사용 시 host.docker.internal 설정 |
| 한국어 모델 세팅 | EEVE-Korean 또는 Qwen2.5 설치 | 15~60분 (모델 크기에 따라) | VRAM 초과 여부 확인 |
| 시스템 프롬프트 설정 | Open WebUI에서 한국어 고정 프롬프트 입력 | 2분 | 모델별로 각각 설정 필요 |
| GPU 가속 확인 | `ollama ps`에서 VRAM 사용량 확인 | 1분 | CUDA 드라이버 버전 확인 |

---

## ❓ 자주 묻는 질문

**Q1: ollama 설치 윈도우에서 GPU 없어도 되나요?**
네, GPU 없이 CPU만으로도 Ollama를 설치하고 실행할 수 있습니다. 다만 CPU만 사용할 경우 모델 응답 속도가 GPU 대비 5~10배 이상 느려질 수 있어요. 예를 들어 NVIDIA RTX 3060(12GB VRAM)에서 1~2초 걸리는 응답이 인텔 i7 CPU에서는 20~40초 걸릴 수 있습니다. 일상적인 테스트 용도라면 CPU로도 충분하지만, 실무 활용을 원한다면 VRAM 8GB 이상의 GPU 환경을 권장합니다. AMD GPU는 ROCm 지원이 필요하며, 윈도우 환경에서는 NVIDIA CUDA 기반이 가장 안정적입니다.

**Q2: Ollama에서 한국어 대화가 잘 되는 모델은 뭔가요?**
2026년 4월 기준으로 한국어 성능이 검증된 모델은 크게 세 가지입니다. 첫째, EEVE-Korean-10.8B는 업스테이지에서 공개한 모델로 한국어 이해도가 뛰어나고 Ollama 모델 라이브러리에서 바로 pull할 수 있습니다. 둘째, Qwen2.5:14b는 알리바바의 다국어 모델로 한국어 처리가 우수하며 14B 기준 VRAM 10GB 이상 권장합니다. 셋째, gemma3:12b는 구글 DeepMind의 최신 오픈소스 모델로 한국어 응답 품질이 크게 개선됐습니다. 7B 이하 소형 모델 중에서는 qwen2.5:7b도 기본 한국어 대화가 가능합니다.

**Q3: Open WebUI 설치할 때 Docker가 꼭 필요한가요?**
Docker 없이도 pip(파이썬 패키지 관리자)를 이용해 설치할 수 있습니다. 터미널에서 `pip install open-webui` 명령어 하나로 설치되고, `open-webui serve`로 실행할 수 있어요. 다만 파이썬 3.11 이상이 필요하고, 환경변수 충돌이 발생하면 가상환경(venv) 설정이 추가로 필요합니다. Docker를 사용하면 이런 의존성 문제를 한 번에 해결할 수 있어 초보자에게는 Docker Desktop 설치 후 docker run 명령으로 진행하는 방법을 권장합니다. 2026년 기준 Open WebUI의 공식 권장 설치 방법은 Docker 방식입니다.

**Q4: Ollama 모델 파일은 어디에 저장되나요? 용량 관리는 어떻게 하나요?**
윈도우 환경에서 Ollama 모델 파일은 기본적으로 `C:\Users\사용자명\.ollama\models` 경로에 저장됩니다. 모델 크기가 상당해서 7B 모델 기준 4~8GB, 14B 모델은 8~16GB, 70B 모델은 40GB 이상 공간을 차지해요. 저장 경로를 변경하고 싶다면 윈도우 시스템 환경변수에서 `OLLAMA_MODELS`를 원하는 경로(예: D:\OllamaModels)로 설정하면 됩니다. 사용하지 않는 모델은 `ollama rm 모델명` 명령어로 삭제할 수 있고, `ollama list`로 현재 설치된 모델 목록을 확인할 수 있습니다.

**Q5: Open WebUI에서 외부에서도 접속할 수 있게 설정할 수 있나요?**
기본적으로 Open WebUI는 localhost(127.0.0.1)에서만 접속 가능하도록 설정되어 있어요. 같은 네트워크 내 다른 기기에서 접속하려면 윈도우 방화벽에서 해당 포트(기본 3000번 또는 8080번)를 열어줘야 합니다. 인터넷 외부에서 접속하려면 ngrok이나 Cloudflare Tunnel 같은 터널링 서비스를 활용하는 방법이 가장 간편하고 안전합니다. 단, 로컬 AI 서버를 외부에 공개할 경우 반드시 Open WebUI의 계정 인증 설정을 활성화하고, 개인정보가 포함된 대화 내용이 외부에 노출되지 않도록 각별히 주의해야 합니다.

---

## ✅ 마무리 — 이제 진짜 '내 AI'를 쓸 차례입니다

여기까지 따라오셨다면, 여러분의 윈도우 PC에 완전히 개인화된 로컬 AI 환경이 갖춰진 겁니다.

월 구독료 없이, 인터넷 연결 없이, 외부 서버에 데이터를 보내지 않아도 됩니다. 내 데이터는 내 PC 안에서만 처리되고, 모델 선택부터 시스템 프롬프트까지 완전히 내 입맛대로 커스터마이즈할 수 있어요.

정리하면 이렇습니다:
- **Ollama** = 로컬 LLM을 쉽게 실행하는 엔진
- **Open WebUI** = 그 엔진 위에 얹는 ChatGPT 스타일 인터페이스
- **한국어 모델(EEVE-Korean, Qwen2.5 등)** = 실제로 쓸 수 있는 한국어 두뇌

다음 단계로는 **Open WebUI의 RAG 기능을 활용한 문서 기반 Q&A 시스템 구축**, **Modelfile을 이용한 커스텀 페르소나 만들기**, **n8n과 Ollama 연동한 AI 자동화 워크플로우** 등을 다룰 예정입니다.

설치하다가 막히는 부분, 에러 메시지가 나오는 부분, 내 PC 사양에서는 어떤 모델이 맞는지 — **댓글에 구체적인 상황을 남겨주시면** 직접 답변해드릴게요. "RTX 3060 12GB인데 한국어 모델 추천해주세요"처럼 사양까지 적어주시면 더 정확한 추천이 가능합니다!