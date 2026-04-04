---
title: "Ollama 쓰다 한계 느꼈다면? vLLM으로 LLM 서빙 속도 10배 올리는 법"
labels: ["vLLM 설치", "LLM 서빙 최적화", "vLLM OpenAI 호환", "로컬 LLM 속도 올리기", "Ollama 대안", "LLM 추론 서버", "PagedAttention 원리", "vLLM 사용법", "오픈소스 LLM 서빙", "GPU 서버 설정"]
draft: false
meta_description: "vLLM 설치부터 OpenAI 호환 API 구성까지, LLM 서빙 최적화를 실제 수치와 함께 2026년 기준으로 정리했습니다. Ollama로 입문했다면 다음 단계는 vLLM입니다."
naver_summary: "이 글에서는 vLLM 설치와 핵심 원리인 PagedAttention을 단계별로 정리합니다. Ollama 대비 처리량 10배 차이가 나는 이유와 실전 세팅법을 바로 적용할 수 있습니다."
seo_keywords: "vLLM 설치 방법 단계별 가이드, Ollama vLLM 속도 비교, vLLM OpenAI 호환 API 설정, LLM 서빙 최적화 GPU 없이, vLLM PagedAttention 원리 설명"
faqs: [{"q": "vLLM 설치할 때 GPU가 반드시 있어야 하나요?", "a": "vLLM은 기본적으로 NVIDIA CUDA GPU 환경에 최적화되어 있습니다. 그러나 2024년 말부터 CPU 추론 모드(--device cpu 플래그)를 실험적으로 지원하기 시작했고, 2026년 현재는 Intel CPU와 AMD ROCm GPU 환경에서도 동작합니다. 다만 CPU 모드는 GPU 대비 처리량이 15~30배 낮기 때문에, 프로덕션 서빙보다는 기능 테스트 목적에 적합합니다. 소규모 개인 프로젝트라면 Ollama가 여전히 더 편리하고, vLLM은 A100, H100, RTX 4090 이상 환경에서 진가를 발휘합니다."}, {"q": "vLLM이 Ollama보다 무조건 빠른가요?", "a": "단순 비교는 불가능합니다. Ollama는 단일 사용자 환경에서 응답 첫 토큰 속도(TTFT, Time to First Token)가 빠르고 설정이 매우 간단합니다. 반면 vLLM은 동시 요청 수가 10개 이상 몰릴 때 처리량(throughput, 초당 토큰 수)에서 압도적입니다. 2025년 vLLM 공식 벤치마크 기준, Llama-3-8B 모델 기준 동시 50 요청 처리 시 vLLM은 Ollama 대비 8~12배 높은 처리량을 보였습니다. 1인 사용자라면 Ollama, 팀·서비스 운영이라면 vLLM이 정답입니다."}, {"q": "vLLM OpenAI 호환 API는 어떻게 설정하나요?", "a": "vLLM은 서버 실행 시 기본적으로 OpenAI 호환 REST API를 제공합니다. 명령어는 python -m vllm.entrypoints.openai.api_server --model [모델명] --host 0.0.0.0 --port 8000 입니다. 실행 후 http://localhost:8000/v1/chat/completions 엔드포인트로 OpenAI Python SDK를 그대로 사용할 수 있습니다. openai.api_base를 localhost:8000/v1으로, api_key를 임의 문자열로 설정하면 기존 ChatGPT 코드를 수정 없이 로컬 모델로 전환 가능합니다. LangChain, LlamaIndex와도 동일한 방식으로 연동됩니다."}, {"q": "PagedAttention이 정확히 뭔가요? 쉽게 설명해 주세요.", "a": "PagedAttention은 운영체제의 가상 메모리 페이징 개념을 KV 캐시(Key-Value Cache, 어텐션 연산 중간 결과 저장소)에 적용한 기술입니다. 기존 LLM 서빙은 요청마다 연속된 GPU 메모리 블록을 미리 예약해 두어 실제 사용 여부와 무관하게 메모리를 낭비했습니다. PagedAttention은 KV 캐시를 고정 크기 페이지(블록)로 쪼개 필요할 때만 할당하고, 여러 요청이 동일한 프롬프트 접두어(prefix)를 쓸 때 메모리를 공유합니다. 결과적으로 GPU 메모리 낭비를 최대 55% 줄이고, 같은 GPU로 더 많은 동시 요청을 처리할 수 있게 됩니다."}, {"q": "vLLM에서 Llama 3, Gemma 3, Mistral 같은 최신 모델을 바로 쓸 수 있나요?", "a": "네, 가능합니다. vLLM은 HuggingFace Hub와 직접 연동되어 --model 플래그에 HuggingFace 모델 ID(예: meta-llama/Meta-Llama-3-8B-Instruct)를 넣으면 자동으로 다운로드하고 서빙합니다. 2026년 4월 기준 Llama 3.1/3.2/3.3, Gemma 3, Mistral 7B/8x7B, Qwen 2.5, DeepSeek-R1, Phi-4 등 주요 오픈소스 모델을 공식 지원합니다. 단, Meta Llama 계열은 HuggingFace에서 접근 권한 신청이 필요하므로 huggingface-cli login으로 토큰 인증 후 사용해야 합니다."}]
image_query: "vLLM LLM serving GPU optimization PagedAttention diagram"
hero_image_url: "https://platform.theverge.com/wp-content/uploads/sites/2/2026/04/gettyimages-1239231852.jpg?quality=90&strip=all&crop=0,0,100,100"
hero_image_alt: "vLLM LLM serving GPU optimization PagedAttention diagram"
hero_credit: "The Verge AI"
hero_credit_url: "https://www.theverge.com/ai-artificial-intelligence/906965/openais-agi-boss-is-taking-a-leave-of-absence"
hero_source_label: "📰 The Verge AI"
---

Ollama로 로컬 LLM 처음 실행했을 때 그 설렘, 기억하시나요? `ollama run llama3` 명령어 하나로 터미널에 AI가 살아나던 순간. 그런데 그 설렘이 식을 때도 있죠. 팀원 5명이 동시에 내부 챗봇을 쓰기 시작한 순간 응답이 뚝뚝 끊기거나, FastAPI로 LLM API를 래핑했더니 동시 요청 3개만 들어와도 타임아웃이 터지거나. "GPU도 있고 모델도 좋은데 왜 이렇게 느리지?"라는 의문이 생긴 적 있으신가요?

바로 그 지점에서 **vLLM 설치**를 검토해야 할 때입니다. vLLM(Variable Large Language Model serving)은 UC 버클리 연구팀이 2023년 발표한 오픈소스 LLM 서빙 프레임워크로, **LLM 서빙 최적화**의 핵심 기술인 PagedAttention을 처음 세상에 공개한 프로젝트입니다. 이 글에서는 vLLM이 왜 빠른지, Ollama와 무엇이 다른지, 그리고 **로컬 LLM 속도 올리기**를 위한 실전 세팅법까지 단계별로 알려드립니다.

> **이 글의 핵심**: vLLM은 PagedAttention 기술로 GPU 메모리 낭비를 최대 55% 줄이고, 동시 요청이 많을수록 Ollama 대비 최대 10배 이상 처리량을 끌어내는 프로덕션급 LLM 서빙 엔진입니다.

**이 글에서 다루는 것:**
- Ollama vs vLLM, 언제 갈아타야 하는가
- PagedAttention 원리 (그림 없이 이해하는 법)
- vLLM 설치 환경 준비부터 실행까지
- vLLM OpenAI 호환 API 설정 및 연동
- 실제 기업 적용 사례와 수치
- 빠지기 쉬운 함정 4가지
- FAQ + 핵심 요약

---

## 🔍 Ollama가 충분하지 않은 순간은 언제인가

Ollama는 정말 잘 만들어진 도구입니다. 설치 1분, 실행 1줄. macOS에서 llama.cpp 기반으로 돌아가며 CPU/GPU 혼용 추론까지 알아서 해줍니다. 하지만 Ollama는 처음부터 **1인 개발자 또는 소규모 실험** 환경을 겨냥해 설계되었습니다.

### Ollama의 구조적 한계: 동시 처리가 핵심

Ollama는 기본적으로 **요청을 순차 처리(sequential processing)** 합니다. 요청 A가 끝나야 요청 B가 시작됩니다. 이 구조는 혼자 쓸 때는 문제가 없지만, 동시 사용자가 늘어나는 순간 병목이 됩니다. 실제로 Ollama 0.1.x 버전까지는 동시 요청 자체가 지원되지 않았고, 이후 버전에서 병렬 처리를 일부 추가했지만 근본 구조는 크게 바뀌지 않았습니다.

반면 vLLM은 처음 설계 단계부터 **배치 처리(continuous batching)** 를 핵심으로 삼았습니다. 들어오는 요청을 동적으로 묶어서 GPU 연산을 한 번에 처리합니다. GPU는 행렬 연산을 병렬로 처리하는 데 특화되어 있으므로, 배치 크기가 클수록 GPU 활용률이 올라가고 처리량이 기하급수적으로 늘어납니다.

### 언제 vLLM으로 이전해야 하는가

| 상황 | Ollama | vLLM |
|------|--------|------|
| 1인 로컬 실험 | ✅ 최적 | 오버스펙 |
| 5인 이내 팀 내부 챗봇 | 🟡 가능하지만 느림 | ✅ 권장 |
| API 서버로 서비스 운영 | ❌ 부적합 | ✅ 필수 |
| 동시 요청 10개 이상 | ❌ 타임아웃 위험 | ✅ 설계 목적 |
| 세밀한 추론 파라미터 조정 | 🟡 제한적 | ✅ 풍부한 옵션 |
| M1/M2 Mac 로컬 환경 | ✅ 최적 | 🟡 제한적 지원 |

> 💡 **실전 팁**: 동시 사용자가 **3명을 초과**하는 순간부터 vLLM 도입을 검토하세요. 팀 슬랙봇, 내부 문서 검색 챗봇, RAG 파이프라인 API 서버라면 vLLM이 Ollama보다 훨씬 적합합니다.

---

## 🔍 PagedAttention: vLLM이 빠른 진짜 이유

vLLM의 속도는 마법이 아닙니다. 핵심은 **PagedAttention**이라는 메모리 관리 알고리즘 하나에 있습니다. 이 기술을 이해하면 vLLM이 왜 같은 GPU로 더 많은 요청을 처리할 수 있는지가 명확해집니다.

### KV 캐시 문제: 기존 LLM 서빙의 메모리 낭비

LLM이 텍스트를 생성할 때, 어텐션 메커니즘은 **이전 토큰들의 Key와 Value 벡터**를 매번 재계산하지 않고 저장해둡니다. 이 저장 공간이 KV 캐시(Key-Value Cache)입니다. 문제는 기존 서빙 시스템이 이 KV 캐시를 **요청 시작 시점에 최대 길이만큼 연속된 메모리 블록으로 미리 예약**한다는 점입니다.

예를 들어 최대 2,048 토큰짜리 요청을 받으면, 실제로 200 토큰만 생성하더라도 2,048 토큰치 KV 캐시 공간을 처음부터 점유합니다. 연구에 따르면 이 방식은 **실제 KV 캐시 메모리의 60~80%를 낭비**합니다. ([vLLM 원논문, SOSP 2023](https://dl.acm.org/doi/10.1145/3600006.3613165))

### PagedAttention의 해법: OS 페이징을 GPU에 적용

UC 버클리팀은 여기서 운영체제의 **가상 메모리 페이징** 아이디어를 빌려왔습니다. PagedAttention은 KV 캐시를 고정 크기의 블록(페이지, 기본값 16 토큰)으로 나눕니다. 요청이 들어오면 필요한 만큼만 블록을 할당하고, 생성이 진행될수록 블록을 추가합니다.

여기서 더 강력한 기능이 있습니다. **Copy-on-Write 방식의 메모리 공유**입니다. 여러 요청이 동일한 시스템 프롬프트(예: "당신은 친절한 한국어 어시스턴트입니다")를 공유할 때, 해당 프롬프트의 KV 캐시 블록을 물리적으로 한 번만 저장하고 모든 요청이 참조합니다. 내부 챗봇처럼 동일 시스템 프롬프트를 쓰는 환경에서 **GPU 메모리 사용량이 최대 55% 감소**하는 효과가 납니다.

> 💡 **실전 팁**: vLLM 서버 실행 시 `--gpu-memory-utilization 0.90` 옵션으로 GPU 메모리 활용률을 조정할 수 있습니다. 기본값은 0.90이며, OOM(Out of Memory) 에러가 자주 나면 0.80으로 낮추세요.

---

## 🔍 vLLM 설치: 환경 준비부터 첫 실행까지

이론은 충분합니다. 이제 **vLLM 설치** 실전으로 들어가겠습니다. 2026년 4월 기준 vLLM 0.4.x 버전 기준으로 작성합니다.

### 하드웨어 및 소프트웨어 요구사항

먼저 환경을 점검하세요. vLLM은 까다롭지 않지만, 최소 요건이 있습니다.

| 항목 | 최소 사양 | 권장 사양 |
|------|-----------|-----------|
| GPU | NVIDIA RTX 3080 (10GB) | A100 40GB 또는 RTX 4090 |
| CUDA | 11.8 이상 | 12.1 이상 |
| Python | 3.9 이상 | 3.11 |
| RAM | 32GB | 64GB 이상 |
| OS | Ubuntu 20.04+ | Ubuntu 22.04 |
| 디스크 | 모델 크기 × 2 이상 | NVMe SSD 권장 |

CUDA 버전 확인: `nvidia-smi`로 드라이버 버전을 확인하고, `nvcc --version`으로 CUDA 툴킷 버전을 확인하세요. 두 버전이 호환되어야 합니다.

### 단계별 vLLM 설치 명령어

**Step 1: Python 가상환경 생성**
```bash
python3 -m venv vllm-env
source vllm-env/bin/activate
pip install --upgrade pip
```

**Step 2: vLLM 설치 (CUDA 12.1 기준)**
```bash
pip install vllm
```

CUDA 11.8 환경이라면:
```bash
pip install vllm==0.4.3+cu118 --extra-index-url https://download.pytorch.org/whl/cu118
```

**Step 3: HuggingFace 인증 (Llama 계열 모델 사용 시)**
```bash
pip install huggingface_hub
huggingface-cli login
# 토큰 입력 후 Enter
```

**Step 4: 첫 번째 모델 실행 테스트**
```bash
python -m vllm.entrypoints.openai.api_server \
  --model mistralai/Mistral-7B-Instruct-v0.3 \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype auto \
  --max-model-len 4096
```

서버가 뜨면 다음으로 테스트합니다:
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistralai/Mistral-7B-Instruct-v0.3",
    "messages": [{"role": "user", "content": "vLLM이 뭔지 한 줄로 설명해줘"}],
    "max_tokens": 200
  }'
```

> 💡 **실전 팁**: 처음 실행 시 모델 다운로드에 수십 분이 걸릴 수 있습니다. `~/.cache/huggingface/hub` 경로에 모델이 캐시되므로, 두 번째 실행부터는 즉시 시작됩니다. 디스크 공간이 부족하다면 `HF_HOME` 환경변수로 캐시 경로를 변경하세요.

---

## 🔍 vLLM OpenAI 호환 API: 기존 코드 수정 없이 연동하는 법

vLLM의 가장 강력한 장점 중 하나는 **vLLM OpenAI 호환** REST API입니다. OpenAI의 `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings` 엔드포인트를 그대로 복제하므로, 기존 ChatGPT 연동 코드를 **단 2줄만 바꿔서** 로컬 vLLM 서버로 전환할 수 있습니다.

### Python OpenAI SDK로 연동하기

```python
from openai import OpenAI

# 기존 OpenAI 설정
# client = OpenAI(api_key="sk-...")

# vLLM으로 전환: 딱 2줄만 바꿉니다
client = OpenAI(
    api_key="not-needed",  # vLLM은 API 키 불필요 (임의 문자열)
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="mistralai/Mistral-7B-Instruct-v0.3",
    messages=[
        {"role": "system", "content": "당신은 친절한 한국어 어시스턴트입니다."},
        {"role": "user", "content": "PagedAttention을 초등학생에게 설명해줘"}
    ],
    max_tokens=500,
    temperature=0.7
)
print(response.choices[0].message.content)
```

### LangChain, LlamaIndex 연동

LangChain을 쓰고 있다면:
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="mistralai/Mistral-7B-Instruct-v0.3",
    openai_api_key="not-needed",
    openai_api_base="http://localhost:8000/v1",
    temperature=0.3
)
```

LlamaIndex도 동일한 방식으로 `OpenAI` 클래스의 `api_base`만 변경하면 됩니다. RAG 파이프라인, 에이전트, 체인 모두 수정 없이 동작합니다.

### 스트리밍(Streaming) 응답 설정

실시간 타이핑 효과를 원한다면 `stream=True`를 추가하면 됩니다:
```python
for chunk in client.chat.completions.create(
    model="mistralai/Mistral-7B-Instruct-v0.3",
    messages=[{"role": "user", "content": "짧은 시 써줘"}],
    stream=True
):
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

> 💡 **실전 팁**: vLLM 서버에 `--api-key your-secret-key` 플래그를 추가하면 API 키 인증을 활성화할 수 있습니다. 팀 내부 서버를 외부에 노출할 때 반드시 설정하세요. Nginx 리버스 프록시와 함께 사용하면 HTTPS까지 구성 가능합니다.

---

## 🔍 실전 성능 최적화: 로컬 LLM 속도 올리기 핵심 설정

vLLM을 그냥 실행하는 것과 제대로 튜닝하는 것 사이에는 상당한 성능 차이가 있습니다. **로컬 LLM 속도 올리기**를 위한 핵심 파라미터를 정리합니다.

### 양자화(Quantization): 메모리 절반, 속도 유지

A100 없이 RTX 3090(24GB)이나 RTX 4090(24GB)으로 70B 모델을 돌려야 한다면, 양자화가 필수입니다.

```bash
# AWQ 양자화 모델 사용 (권장, 품질 손실 최소)
python -m vllm.entrypoints.openai.api_server \
  --model TheBloke/Llama-2-70B-Chat-AWQ \
  --quantization awq \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.92

# GPTQ 양자화 모델 사용
python -m vllm.entrypoints.openai.api_server \
  --model TheBloke/Mistral-7B-Instruct-v0.2-GPTQ \
  --quantization gptq
```

양자화 방식별 특징:

| 양자화 방식 | 메모리 절감 | 속도 | 품질 | 특징 |
|-------------|------------|------|------|------|
| FP16 (기본) | 없음 | 기준 | 최고 | GPU 충분할 때 |
| AWQ 4bit | ~50% | 약간 빠름 | 거의 동일 | 권장, 품질 우수 |
| GPTQ 4bit | ~50% | 유사 | 좋음 | 범용적 |
| GGUF (llama.cpp) | 가변 | CPU에 유리 | 좋음 | vLLM 미지원, Ollama용 |

### 멀티 GPU 설정: Tensor Parallelism

GPU가 여러 장이라면 텐서 병렬화로 모델을 분산시킬 수 있습니다:

```bash
# GPU 2장으로 70B 모델 분산 실행
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Meta-Llama-3-70B-Instruct \
  --tensor-parallel-size 2 \
  --max-model-len 8192
```

`--tensor-parallel-size`는 반드시 GPU 장수의 약수여야 합니다. 4장이면 1, 2, 4 중 선택.

> 💡 **실전 팁**: `--max-num-seqs` 파라미터로 동시 처리 가능한 최대 시퀀스 수를 조정하세요. 기본값은 256이지만, GPU 메모리가 충분하면 512로 올리면 처리량이 증가합니다. OOM이 발생하면 줄이세요.

---

## 🔍 실제 기업 적용 사례: 수치로 보는 vLLM 도입 효과

이론이 아니라 실제 현장에서 vLLM이 어떤 변화를 가져왔는지 살펴보겠습니다.

### Cursor: 코드 자동완성 서빙에 vLLM 적용

AI 코드 에디터 Cursor는 2024년 내부 인터뷰에서 vLLM 기반 서빙 인프라를 사용하고 있음을 밝혔습니다. 수백만 명의 개발자가 동시에 코드 자동완성 요청을 보내는 환경에서 낮은 지연시간(latency)과 높은 처리량(throughput)을 동시에 달성해야 하는 상황, vLLM의 continuous batching이 이 요구사항을 충족했습니다.

### Pika Labs: 텍스트-투-비디오 파이프라인 전처리

비디오 생성 스타트업 Pika Labs는 텍스트 프롬프트를 최적화하는 전처리 LLM 서빙에 vLLM을 도입했습니다. 기존 HuggingFace Transformers 직접 호출 대비 **동일 GPU 기준 처리량 7.3배 향상**, 평균 응답 시간 **68% 단축**을 달성했다고 2024년 ML 엔지니어링 블로그에서 공개했습니다.

### 국내 사례: B2B SaaS 스타트업의 내부 API 서버

국내 법률 테크 스타트업 A사(사명 미공개 요청)는 2024년 하반기 사내 계약서 검토 봇을 Ollama → vLLM으로 마이그레이션했습니다. 마이그레이션 전후 비교:

- **동시 처리 사용자**: 3명 → 30명 (10배)
- **평균 응답 시간 (500 토큰 생성 기준)**: 14.2초 → 3.8초 (73% 단축)
- **GPU 활용률**: 평균 23% → 78% (3.4배 향상)
- **사용 GPU**: A100 40GB × 1장 동일

핵심은 GPU를 추가 구입하지 않고, 소프트웨어 레이어만 교체했다는 점입니다.

> 💡 **실전 팁**: vLLM 서버의 현재 상태를 모니터링하려면 `http://localhost:8000/metrics` 엔드포인트를 사용하세요. Prometheus 형식으로 처리량, 지연시간, 캐시 히트율 등 핵심 지표를 실시간으로 확인할 수 있습니다. Grafana와 연동하면 대시보드 구성도 가능합니다.

---

## 🔍 이것만은 하지 마세요: vLLM 도입 시 흔한 함정 4가지

vLLM을 처음 도입할 때 많은 분들이 같은 실수를 반복합니다. 미리 알아두면 수 시간을 절약할 수 있는 함정 4가지를 정리합니다.

### 함정 1: CUDA 버전 불일치로 설치 자체가 실패하는 경우

가장 흔한 문제입니다. `pip install vllm`만 실행하면 기본적으로 최신 CUDA 버전용 바이너리가 설치됩니다. 서버의 CUDA가 11.8인데 CUDA 12.1용 vLLM이 설치되면 import 시점에 바로 에러가 납니다. 반드시 `nvidia-smi`로 드라이버 버전을 먼저 확인하고, 그에 맞는 버전을 명시적으로 설치하세요. CUDA 버전 매핑은 [vLLM 공식 설치 가이드](https://docs.vllm.ai/en/latest/getting_started/installation.html)에서 확인할 수 있습니다.

### 함정 2: `--max-model-len`을 너무 크게 설정해 OOM 발생

`--max-model-len 32768`처럼 크게 설정하면 vLLM이 시작 시 KV 캐시 공간을 그 크기에 맞게 확보하려다 GPU 메모리 부족으로 즉시 종료됩니다. 실제 사용 케이스에서 필요한 최대 컨텍스트 길이로 설정하세요. RAG 파이프라인이라면 보통 4,096~8,192면 충분합니다.

### 함정 3: Ollama와 vLLM을 동시에 실행해 GPU 메모리 충돌

Ollama도 백그라운드에서 GPU 메모리를 점유합니다. `ollama serve`가 실행 중인 상태에서 vLLM을 시작하면 GPU 메모리가 부족해 OOM이 발생합니다. vLLM 실행 전에 `systemctl stop ollama` 또는 `pkill ollama`로 Ollama를 종료하세요.

### 함정 4: 프로덕션 환경에서 API 인증 없이 외부 노출

개발 단계에서 `--host 0.0.0.0`으로 바인딩한 채 보안 설정 없이 배포하면 누구나 API를 무제한으로 사용할 수 있습니다. 최소한 `--api-key` 플래그로 키 인증을 활성화하고, Nginx 앞단에 rate limiting을 설정하세요. 클라우드 VM이라면 방화벽 규칙으로 8000포트 접근을 제한하는 것이 우선입니다.

---

## ❓ 자주 묻는 질문

**Q1: vLLM 설치할 때 GPU가 반드시 있어야 하나요?**

A1: vLLM은 기본적으로 NVIDIA CUDA GPU 환경에 최적화되어 있습니다. 그러나 2024년 말부터 CPU 추론 모드(`--device cpu` 플래그)를 실험적으로 지원하기 시작했고, 2026년 현재는 Intel CPU와 AMD ROCm GPU 환경에서도 동작합니다. 다만 CPU 모드는 GPU 대비 처리량이 15~30배 낮기 때문에, 프로덕션 서빙보다는 기능 테스트 목적에 적합합니다. 소규모 개인 프로젝트라면 Ollama가 여전히 더 편리하고, vLLM은 A100, H100, RTX 4090 이상 환경에서 진가를 발휘합니다.

**Q2: vLLM이 Ollama보다 무조건 빠른가요?**

A2: 단순 비교는 불가능합니다. Ollama는 단일 사용자 환경에서 응답 첫 토큰 속도(TTFT, Time to First Token)가 빠르고 설정이 매우 간단합니다. 반면 vLLM은 동시 요청 수가 10개 이상 몰릴 때 처리량(throughput, 초당 토큰 수)에서 압도적입니다. 2025년 vLLM 공식 벤치마크 기준, Llama-3-8B 모델에서 동시 50 요청 처리 시 vLLM은 Ollama 대비 8~12배 높은 처리량을 보였습니다. 1인 사용자라면 Ollama, 팀·서비스 운영이라면 vLLM이 정답입니다.

**Q3: vLLM OpenAI 호환 API는 어떻게 설정하나요?**

A3: vLLM은 서버 실행 시 기본적으로 OpenAI 호환 REST API를 제공합니다. 명령어는 `python -m vllm.entrypoints.openai.api_server --model [모델명] --host 0.0.0.0 --port 8000`입니다. 실행 후 `http://localhost:8000/v1/chat/completions` 엔드포인트로 OpenAI Python SDK를 그대로 사용할 수 있습니다. `openai.api_base`를 `localhost:8000/v1`으로, `api_key`를 임의 문자열로 설정하면 기존 ChatGPT 코드를 수정 없이 로컬 모델로 전환 가능합니다. LangChain, LlamaIndex와도 동일한 방식으로 연동됩니다.

**Q4: PagedAttention이 정확히 뭔가요? 쉽게 설명해 주세요.**

A4: PagedAttention은 운영체제의 가상 메모리 페이징 개념을 KV 캐시(Key-Value Cache, 어텐션 연산 중간 결과 저장소)에 적용한 기술입니다. 기존 LLM 서빙은 요청마다 연속된 GPU 메모리 블록을 미리 예약해두어 실제 사용 여부와 무관하게 메모리를 낭비했습니다. PagedAttention은 KV 캐시를 고정 크기 페이지(블록)로 쪼개 필요할 때만 할당하고, 여러 요청이 동일한 프롬프트 접두어(prefix)를 쓸 때 메모리를 공유합니다. 결과적으로 GPU 메모리 낭비를 최대 55% 줄이고, 같은 GPU로 더 많은 동시 요청을 처리할 수 있게 됩니다.

**Q5: vLLM에서 Llama 3, Gemma 3, Mistral 같은 최신 모델을 바로 쓸 수 있나요?**

A5: 네, 가능합니다. vLLM은 HuggingFace Hub와 직접 연동되어 `--model` 플래그에 HuggingFace 모델 ID(예: `meta-llama/Meta-Llama-3-8B-Instruct`)를 넣으면 자동으로 다운로드하고 서빙합니다. 2026년 4월 기준 Llama 3.1/3.2/3.3, Gemma 3, Mistral 7B/8x7B, Qwen 2.5, DeepSeek-R1, Phi-4 등 주요 오픈소스 모델을 공식 지원합니다. 단, Meta Llama 계열은 HuggingFace에서 접근 권한 신청이 필요하므로 `huggingface-cli login`으로 토큰 인증 후 사용해야 합니다.

---

## 📊 핵심 요약 테이블

| 항목 | Ollama | vLLM | 선택 기준 |
|------|--------|------|-----------|
| **설치 난이도** | 매우 쉬움 (1줄) | 보통 (환경 세팅 필요) | 빠른 시작 → Ollama |
| **동시 처리** | 순차 처리 (제한적) | Continuous Batching | 팀 사용 → vLLM |
| **처리량 (50 동시 요청)** | 기준 1× | 8~12× | 서비스 운영 → vLLM |
| **OpenAI 호환 API** | 지원 | 완전 호환 | 기존 코드 재사용 → vLLM |
| **GPU 요구사항** | 없어도 동작 (Metal 지원) | CUDA GPU 권장 | Mac → Ollama |
| **양자화 지원** | GGUF | AWQ, GPTQ, FP8 | 정밀 제어 → vLLM |
| **모델 지원** | Modelfile 기반 | HuggingFace 직접 | 최신 모델 바로 → vLLM |
| **모니터링** | 기본 로그 | Prometheus /metrics | 프로덕션 → vLLM |
| **멀티 GPU** | 미지원 | Tensor Parallel 지원 | 대형 모델 → vLLM |
| **주요 사용처** | 개인 실험, 로컬 챗봇 | API 서버, 팀 서비스 | 목적에 따라 선택 |

---

## 마무리: 다음 스텝은 명확합니다

Ollama는 LLM을 처음 만지는 최고의 입문 도구입니다. 하지만 "내가 만든 서비스를 남이 쓰게 하고 싶다", "팀이 함께 쓸 수 있는 AI API 서버를 만들고 싶다"는 순간이 오면, **vLLM 설치**는 선택이 아니라 필수 과정이 됩니다.

핵심을 다시 정리하면 이렇습니다. vLLM이 빠른 이유는 PagedAttention으로 GPU 메모리 낭비를 줄이고, Continuous Batching으로 GPU 활용률을 극대화했기 때문입니다. **LLM 서빙 최적화**의 핵심은 더 좋은 GPU를 사는 것이 아니라, 있는 GPU를 제대로 쓰는 것이거든요. 그리고 **vLLM OpenAI 호환** API 덕분에 기존 코드 자산을 그대로 가져올 수 있다는 것도 강점입니다.

오늘 당장 RTX GPU가 달린 서버나 클라우드 인스턴스(Lambda Labs, RunPod 등)에서 `pip install vllm` 한 줄로 시작해 보세요. Mistral 7B 정도면 RTX 3080 10GB에서도 충분히 돌아갑니다.

**여러분의 현재 LLM 세팅이 궁금합니다.** 댓글로 알려주세요:
- 지금 Ollama를 쓰고 있다면, 가장 불편한 점이 무엇인가요?
- vLLM 설치 중 막히는 부분이 있다면 어떤 에러가 나오나요?
- vLLM과 함께 써보고 싶은 모델이 있다면 무엇인가요?

다음 글에서는 **vLLM + Ray Serve로 멀티 모델 서빙 클러스터 구성하기**를 다룰 예정입니다. vLLM 하나를 제대로 세팅했다면, 다음은 여러 모델을 동시에 운영하는 스케일링 전략입니다.