#!/usr/bin/env python3
"""AI키퍼 블로그 — 주제 자동 발굴 v3
도메인 116개, 앵글 875개, 중복방지, 도메인 로테이션
"""
import os, sys, re, subprocess, tempfile, datetime, hashlib, json, time, math
import urllib.request, urllib.parse

import anthropic as _anthropic

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://internal-apigw-kr.hmg-corp.io/hchat-in/api/v3/claude"
)
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
BRAVE_API_KEY   = os.environ.get("BRAVE_API_KEY", "")

TODAY   = datetime.date.today().isoformat()
YEAR_WW = datetime.date.today().strftime("%Y-W%V")
DAILY_DOMAINS_COUNT = 20

# ── AI 도메인 ─────────────────────────────────────────────────────────────────
AI_DOMAINS = [
    # 기존 15개
    "ChatGPT OpenAI",
    "Claude Anthropic",
    "Gemini Google AI",
    "Manus AI 에이전트",
    "LLM 언어모델",
    "AI 에이전트 자동화",
    "멀티모달 AI",
    "AI 코딩 개발",
    "프롬프트 엔지니어링",
    "AI 논문 연구",
    "딥러닝 머신러닝",
    "AI 생산성 활용",
    "RAG 벡터DB",
    "오픈소스 AI 모델",
    "AI 규제 정책",

    # AI 모델/서비스
    "Grok xAI",
    "Llama Meta AI",
    "Mistral AI",
    "Perplexity AI",
    "Copilot Microsoft AI",
    "DeepSeek AI 모델",
    "Qwen Alibaba AI",
    "Phi Microsoft 소형LLM",
    "Command R Cohere",
    "Stable Diffusion 이미지생성",
    "Midjourney AI 아트",
    "DALL-E OpenAI 이미지",
    "Runway Gen AI 영상",
    "Sora OpenAI 영상생성",
    "ElevenLabs AI 음성",
    "Whisper 음성인식",
    "HuggingFace 오픈소스",

    # AI 응용/산업
    "AI 헬스케어 의료",
    "AI 교육 에듀테크",
    "AI 법률 리걸테크",
    "AI 금융 핀테크",
    "AI 부동산",
    "AI 마케팅 광고",
    "AI 게임 개발",
    "AI 음악 작곡",
    "AI 영상편집",
    "AI 번역 언어",
    "AI 검색엔진",
    "AI 사이버보안",
    "AI 로보틱스 자율주행",
    "AI 제조 스마트팩토리",
    "AI 농업 푸드테크",

    # AI 기술/개념
    "파인튜닝 LoRA PEFT",
    "양자화 GGUF llama.cpp",
    "컨텍스트 윈도우 LLM",
    "AI 할루시네이션 해결",
    "Mixture of Experts MoE",
    "AI 멀티에이전트 시스템",
    "컴퓨터 비전 YOLO",
    "강화학습 RLHF",
    "AI 워크플로우 n8n",
    "벡터 데이터베이스 Pinecone Chroma",
    "LangChain LlamaIndex",
    "AI API 통합",
    "엣지 AI 온디바이스",
    "AI 칩 반도체 NVIDIA",
    "Transformer 아키텍처",

    # AI 트렌드/비즈니스
    "AI 스타트업 투자",
    "AI 일자리 취업",
    "AI 윤리 편향",
    "AI 저작권 지적재산",
    "AI 규제 EU AI Act",
    "AI 데이터센터 전력",
    "오픈소스 vs 클로즈드 AI",
    "AI 구독 서비스 비교",
    "AI 생산성 측정",
    "AI PC 노트북 추천",
    "AI 스마트폰 온디바이스",
    "AI 웨어러블",

    # 한국/글로벌 AI
    "한국 AI 정책 NIPA",
    "네이버 CLOVA AI",
    "카카오 AI",
    "삼성 AI",
    "SK AI 투자",
    "KT AI",
    "국내 AI 스타트업",

    # ── 신규 추가 도메인 (토픽 풀 확장) ──────────────────────────────────────────
    # AI 모델 추가
    "Phi Microsoft 소형모델",
    "Llava 멀티모달",
    "DALL-E 이미지생성",
    "Sora OpenAI 영상",
    "Kling AI 영상생성",
    "Pika Labs 영상",
    "Luma Dream Machine",

    # AI 개발/인프라
    "Ollama 로컬 LLM",
    "vLLM 추론 최적화",
    "Triton 추론서버",
    "LangSmith 모니터링",
    "Weights Biases MLOps",
    "Dify AI 플랫폼",
    "Flowise AI 빌더",
    "CrewAI 멀티에이전트",
    "AutoGen 에이전트",
    "LlamaFactory 파인튜닝",

    # AI 응용 확장
    "AI 법률 계약서 검토",
    "AI 세무 회계 자동화",
    "AI 의료 영상 진단",
    "AI 약물 개발",
    "AI 기후 환경",
    "AI 스포츠 분석",
    "AI 패션 디자인",
    "AI 건축 도시계획",
    "AI 물류 공급망",
    "AI 금융 리스크",

    # 국내/아시아 AI
    "일본 AI 정책 기업",
    "중국 AI 규제 현황",
    "유럽 AI Act 규제",
    "인도 AI 스타트업",
    "동남아 AI 시장",
    "SK텔레콤 AI",
    "LG AI 연구원",
    "현대 AI 모빌리티",
]


# ── 세부 토픽 앵글 ────────────────────────────────────────────────────────────
TOPIC_SUBTYPES = {
    "ChatGPT OpenAI": [
        "최신 업데이트 변경사항",
        "API 비용 계산 및 최적화",
        "Custom GPT 만들기 실전",
        "프롬프트 엔지니어링 실전 템플릿",
        "o3/o4 추론 모델 심층 분석",
        "업무별 활용 사례 (회계/법무/마케팅)",
        "ChatGPT vs 경쟁사 성능 벤치마크",
        "플러그인 및 GPT Store 추천",
        "코딩 어시스턴트로 활용하기",
        "ChatGPT 한국어 성능 분석",
        "엔터프라이즈 도입 사례",
        "무료 vs 유료 플랜 비교",
        "보안 및 개인정보 이슈",
        "교육 현장 활용 방법",
        "ChatGPT로 콘텐츠 제작하기",
    ],
    "Claude Anthropic": [
        "Claude 최신 버전 기능 변경사항",
        "Claude vs ChatGPT 실전 비교",
        "긴 문서 분석에 Claude 활용하기",
        "Claude API 연동 실습",
        "Constitutional AI 안전성 원리",
        "코드 리뷰 및 디버깅 활용법",
        "Claude Projects 기능 완벽 가이드",
        "Claude 한국어 성능 심층 테스트",
        "연구/논문 작성에 Claude 쓰기",
        "Claude Computer Use 실전 활용",
        "Artifacts 기능으로 앱 만들기",
        "비용 대비 성능 최적화",
        "Claude 모델 선택 가이드 (Haiku/Sonnet/Opus)",
        "멀티턴 대화 전략",
    ],
    "Gemini Google AI": [
        "Gemini 최신 버전 업데이트",
        "Gemini vs GPT-4 성능 비교",
        "Google Workspace 통합 활용",
        "Gemini Advanced 기능 완전 분석",
        "멀티모달 능력 심층 테스트",
        "Gemini API로 앱 만들기",
        "Google Search에서 AI 활용",
        "Gemini 코딩 어시스턴트 활용",
        "NotebookLM 실전 활용법",
        "Gemini Flash vs Pro 선택 기준",
        "Android AI 기능 활용하기",
        "Gemini 한국어 성능 평가",
        "기업용 Gemini for Business",
    ],
    "Grok xAI": [
        "Grok 최신 기능 업데이트",
        "Grok vs ChatGPT 실전 비교",
        "실시간 인터넷 검색 기능 활용",
        "X(트위터) 통합 AI 활용법",
        "Grok 무료 사용 방법",
        "Grok API 활용하기",
        "Grok의 검열 없는 응답 특징 분석",
        "Grok 이미지 생성 기능",
        "SuperGrok 구독 가치 분석",
    ],
    "Llama Meta AI": [
        "Llama 최신 모델 성능 분석",
        "로컬에서 Llama 실행하기",
        "Llama 파인튜닝 실전 가이드",
        "Meta AI 서비스 활용법",
        "Llama.cpp로 PC에서 돌리기",
        "Llama vs GPT 오픈소스 비교",
        "Llama 기반 맞춤형 AI 만들기",
        "Llama Guard 안전성 적용",
        "기업용 Llama 도입 사례",
        "Llama 멀티언어 성능 테스트",
    ],
    "Mistral AI": [
        "Mistral 모델 라인업 정리",
        "Mistral vs Llama 성능 비교",
        "Mixtral MoE 아키텍처 설명",
        "로컬 실행 방법 완전 가이드",
        "Mistral API 활용 실습",
        "유럽 AI의 강자 Mistral 분석",
        "Mistral 파인튜닝 가이드",
        "Le Chat 서비스 활용법",
        "비용 효율 최고 모델 선택",
    ],
    "DeepSeek AI 모델": [
        "DeepSeek 최신 모델 성능 분석",
        "DeepSeek vs GPT-4 비교",
        "DeepSeek 로컬 실행 가이드",
        "DeepSeek R1 추론 능력 분석",
        "중국 AI의 급부상 배경 분석",
        "DeepSeek API 연동 실습",
        "DeepSeek 보안 이슈 정리",
        "DeepSeek 오픈소스 활용하기",
        "DeepSeek Coder 코딩 활용",
    ],
    "Perplexity AI": [
        "Perplexity AI 완전 활용 가이드",
        "Perplexity vs Google 검색 비교",
        "Perplexity Pro 기능 분석",
        "AI 검색의 미래 Perplexity 분석",
        "Perplexity API 연동",
        "리서치 자동화에 Perplexity 쓰기",
        "Perplexity Space 기능 활용",
        "할루시네이션 최소화 전략",
    ],
    "Copilot Microsoft AI": [
        "Microsoft Copilot 전 제품 정리",
        "GitHub Copilot 코딩 활용법",
        "Word/Excel/PowerPoint Copilot 실전",
        "Microsoft 365 Copilot 도입 가이드",
        "Copilot Studio 커스터마이징",
        "Azure AI 서비스 연동",
        "Teams AI 기능 활용",
        "Copilot+ PC 기능 완전 분석",
        "Copilot vs ChatGPT 기업용 비교",
    ],
    "Qwen Alibaba AI": [
        "Qwen 모델 성능 벤치마크",
        "Qwen 로컬 실행 방법",
        "중국 오픈소스 AI 현황",
        "Qwen VL 멀티모달 기능",
        "Qwen API 활용하기",
        "Qwen 한국어 성능 테스트",
        "알리바바 AI 전략 분석",
    ],
    "Stable Diffusion 이미지생성": [
        "Stable Diffusion 완전 초보 가이드",
        "AUTOMATIC1111 vs ComfyUI 비교",
        "LoRA 모델 적용 실전",
        "프롬프트 작성법 마스터하기",
        "최신 모델 SDXL/SD3 분석",
        "Control Net 활용 완벽 가이드",
        "인물 사진 생성 고급 기법",
        "상업적 이용 가능한 모델 정리",
        "로컬 vs 클라우드 실행 비교",
        "AI 이미지 저작권 이슈",
        "실사 vs 애니메이션 스타일 설정",
    ],
    "Midjourney AI 아트": [
        "Midjourney v7 완전 가이드",
        "프롬프트 마스터 클래스",
        "Midjourney로 상업용 이미지 만들기",
        "스타일 일관성 유지하기",
        "캐릭터 디자인 실전",
        "Midjourney vs DALL-E vs Stable Diffusion",
        "웹툰/만화 스타일 생성",
        "로고 및 브랜딩에 활용",
        "Midjourney 구독 플랜 비교",
        "인스타그램 콘텐츠 제작",
    ],
    "DALL-E OpenAI 이미지": [
        "DALL-E 3 완전 활용 가이드",
        "ChatGPT에서 이미지 생성하기",
        "DALL-E API 연동 실습",
        "텍스트 포함 이미지 생성 팁",
        "DALL-E vs Midjourney 비교",
        "상업 목적 이용 가이드",
        "이미지 편집 기능 inpainting",
    ],
    "Runway Gen AI 영상": [
        "Runway Gen-3 영상 생성 가이드",
        "AI 영상 제작 워크플로우",
        "Runway vs Sora 비교",
        "영화/광고 제작에 AI 활용",
        "Runway API 연동",
        "모션 브러시 기능 활용",
        "AI 영상 편집 실전 팁",
    ],
    "Sora OpenAI 영상생성": [
        "Sora 최신 기능 및 업데이트",
        "Sora 접근 방법 가이드",
        "Sora로 영상 제작 실전",
        "Sora vs Runway vs Pika 비교",
        "AI 영상 생성 미래 전망",
        "영상 제작 산업 변화 분석",
        "Sora 프롬프트 최적화",
    ],
    "ElevenLabs AI 음성": [
        "ElevenLabs 완전 활용 가이드",
        "음성 복제(Voice Cloning) 실전",
        "팟캐스트 AI 제작 워크플로우",
        "ElevenLabs API 연동 실습",
        "AI 더빙 실전 활용",
        "TTS 서비스 비교 (ElevenLabs vs 경쟁사)",
        "한국어 AI 음성 품질 분석",
        "유튜브 AI 나레이션 제작",
    ],
    "Whisper 음성인식": [
        "Whisper 로컬 실행 완전 가이드",
        "회의록 자동화 실전",
        "Whisper API 연동",
        "한국어 인식 정확도 테스트",
        "실시간 자막 생성 방법",
        "Whisper vs 경쟁 STT 비교",
        "영상 자동 자막 생성 워크플로우",
        "다국어 번역 동시 처리",
    ],
    "HuggingFace 오픈소스": [
        "HuggingFace 완전 초보 가이드",
        "모델 허브에서 모델 불러오기",
        "Transformers 라이브러리 실습",
        "Spaces로 AI 앱 배포하기",
        "HuggingFace로 파인튜닝하기",
        "Inference API 활용",
        "Datasets 라이브러리 활용",
        "오픈소스 AI 생태계 분석",
        "HuggingFace Pro 기능 정리",
    ],
    "LLM 언어모델": [
        "LLM 작동 원리 쉽게 이해하기",
        "LLM 성능 벤치마크 완전 정리",
        "LLM 선택 가이드 (용도별)",
        "LLM 파인튜닝 vs RAG 비교",
        "LLM 환각(hallucination) 원인과 해결",
        "소형 LLM(SLM) 활용 사례",
        "LLM 컨텍스트 길이 활용법",
        "LLM API 비용 비교",
        "멀티모달 LLM 최신 동향",
        "LLM 보안 취약점 분석",
    ],
    "멀티모달 AI": [
        "멀티모달 AI 개념 완전 정리",
        "이미지+텍스트 AI 활용 사례",
        "영상 이해 AI 최신 동향",
        "음성+비전 멀티모달 실전",
        "멀티모달 모델 성능 비교",
        "멀티모달 API 연동 실습",
        "실무에서 멀티모달 AI 쓰기",
    ],
    "AI 코딩 개발": [
        "AI 코딩 툴 완전 비교 (Copilot/Cursor/Cline)",
        "Cursor AI 완전 활용 가이드",
        "AI로 풀스택 앱 만들기",
        "코드 리뷰 자동화 실전",
        "AI 페어 프로그래밍 워크플로우",
        "테스트 코드 자동 생성",
        "레거시 코드 리팩토링 AI 활용",
        "AI 코딩 보안 이슈 주의점",
        "개발자 생산성 AI 도구 모음",
        "Devin AI 에이전트 분석",
        "Windsurf vs Cursor 비교",
        "AI로 API 문서 자동화",
    ],
    "프롬프트 엔지니어링": [
        "프롬프트 엔지니어링 기초 완전 정리",
        "Chain of Thought 프롬프트 실전",
        "Few-shot vs Zero-shot 비교",
        "역할 부여(Role Prompting) 고급 기법",
        "업무별 프롬프트 템플릿 모음",
        "프롬프트 인젝션 공격과 방어",
        "시스템 프롬프트 설계 전략",
        "출력 형식 제어 기법",
        "프롬프트 최적화 자동화",
        "멀티턴 대화 프롬프트 설계",
    ],
    "딥러닝 머신러닝": [
        "딥러닝 vs 머신러닝 차이 완전 정리",
        "CNN 이미지 인식 원리",
        "RNN/LSTM 시계열 분석",
        "GAN 생성 모델 원리",
        "모델 학습 최적화 기법",
        "과적합 방지 실전 전략",
        "PyTorch vs TensorFlow 비교",
        "ML 파이프라인 구축",
        "데이터 전처리 실전",
        "ML 모델 배포(MLOps)",
    ],
    "RAG 벡터DB": [
        "RAG 완전 초보 가이드",
        "벡터 데이터베이스 종류 비교",
        "RAG vs 파인튜닝 선택 기준",
        "RAG 시스템 구축 실전",
        "임베딩 모델 선택 가이드",
        "RAG 성능 최적화 기법",
        "Hybrid Search 구현",
        "기업 문서 RAG 구축 사례",
        "RAG 평가 지표 및 방법",
        "GraphRAG 최신 동향",
    ],
    "파인튜닝 LoRA PEFT": [
        "파인튜닝 vs RAG 완전 비교",
        "LoRA 원리 쉽게 이해하기",
        "QLoRA로 저사양 GPU 파인튜닝",
        "파인튜닝 데이터셋 준비 방법",
        "Unsloth로 빠른 파인튜닝",
        "파인튜닝 평가 및 검증",
        "도메인 특화 모델 만들기",
        "파인튜닝 비용 최소화 전략",
        "PEFT 기법 총정리",
    ],
    "양자화 GGUF llama.cpp": [
        "양자화 개념 쉽게 이해하기",
        "GGUF 파일 포맷 완전 정리",
        "llama.cpp 설치 및 실행 가이드",
        "Ollama로 로컬 AI 구축",
        "양자화 Q4 vs Q8 성능 비교",
        "CPU에서 LLM 실행하기",
        "저사양 PC에서 AI 돌리기",
        "LM Studio 완전 활용 가이드",
        "모델 양자화 직접 해보기",
    ],
    "컨텍스트 윈도우 LLM": [
        "컨텍스트 윈도우란 무엇인가",
        "긴 컨텍스트 모델 비교 (128K/200K/1M)",
        "컨텍스트 윈도우 효율 활용법",
        "Lost in the Middle 문제 해결",
        "긴 문서 처리 전략",
        "컨텍스트 압축 기법",
        "RAG vs 긴 컨텍스트 선택 기준",
    ],
    "AI 할루시네이션 해결": [
        "AI 환각(hallucination) 원인 완전 분석",
        "환각 감지 및 검증 방법",
        "팩트 체크 AI 도구 모음",
        "RAG로 환각 줄이기",
        "프롬프트로 환각 최소화",
        "의료/법률 AI 신뢰성 문제",
        "환각 평가 벤치마크 분석",
        "Citation 포함 AI 응답 만들기",
    ],
    "Mixture of Experts MoE": [
        "MoE 아키텍처 원리 설명",
        "GPT-4의 MoE 구조 분석",
        "MoE vs Dense 모델 비교",
        "Mixtral MoE 실전 활용",
        "MoE 모델 로컬 실행",
        "MoE의 장단점 완전 분석",
        "MoE 최신 연구 동향",
    ],
    "AI 멀티에이전트 시스템": [
        "멀티에이전트 시스템 개념 정리",
        "AutoGen 완전 활용 가이드",
        "CrewAI 실전 구축",
        "에이전트 오케스트레이션 전략",
        "멀티에이전트 vs 단일에이전트",
        "에이전트 메모리 관리",
        "자율 AI 에이전트 위험성",
        "기업 업무 자동화 에이전트 구축",
        "에이전트 평가 방법",
    ],
    "컴퓨터 비전 YOLO": [
        "YOLO 최신 버전 완전 정리",
        "객체 감지 실전 프로젝트",
        "얼굴 인식 AI 구현",
        "의료 영상 분석 AI",
        "자율주행 비전 시스템",
        "CCTV AI 분석 시스템 구축",
        "OpenCV + AI 실전",
        "이미지 분류 모델 만들기",
        "비전 AI 상업 활용 사례",
    ],
    "강화학습 RLHF": [
        "강화학습 기초 완전 정리",
        "RLHF란 무엇인가",
        "ChatGPT가 RLHF를 쓰는 이유",
        "DPO vs RLHF 비교",
        "게임 AI 강화학습 사례",
        "로봇 제어 강화학습",
        "강화학습 최신 연구 동향",
        "PPO 알고리즘 설명",
    ],
    "AI 워크플로우 n8n": [
        "n8n 완전 초보 가이드",
        "n8n vs Zapier vs Make 비교",
        "n8n으로 AI 자동화 구축",
        "n8n 셀프호스팅 설치 가이드",
        "업무 자동화 실전 사례 10개",
        "AI Agent 노드 활용",
        "n8n + Claude/ChatGPT 연동",
        "노코드 AI 자동화 워크플로우",
        "n8n 템플릿 추천 모음",
    ],
    "벡터 데이터베이스 Pinecone Chroma": [
        "벡터 DB 완전 비교 (Pinecone/Chroma/Weaviate/Qdrant)",
        "Chroma 로컬 설치 실습",
        "Pinecone 클라우드 활용 가이드",
        "벡터 임베딩 이해하기",
        "벡터 DB 성능 최적화",
        "벡터 DB 비용 비교",
        "RAG 시스템에 벡터 DB 연동",
        "시맨틱 검색 구현하기",
    ],
    "LangChain LlamaIndex": [
        "LangChain 완전 초보 가이드",
        "LlamaIndex vs LangChain 비교",
        "LangChain으로 RAG 구축",
        "LangGraph 에이전트 워크플로우",
        "LlamaIndex 문서 분석 실전",
        "LangChain 비용 최적화",
        "LangSmith 모니터링 활용",
        "LangChain 최신 버전 변경사항",
        "프로덕션 LangChain 배포",
    ],
    "AI API 통합": [
        "OpenAI API 완전 가이드",
        "API 비용 최적화 전략",
        "여러 AI API 동시 활용",
        "AI API 보안 처리",
        "API Rate Limit 대응",
        "Streaming 응답 구현",
        "Function Calling 실전",
        "AI API 오류 처리 전략",
        "API 모니터링 및 로깅",
    ],
    "엣지 AI 온디바이스": [
        "온디바이스 AI 개념 정리",
        "Apple Silicon AI 성능 분석",
        "Snapdragon X AI 기능",
        "스마트폰 AI 비교",
        "엣지 AI 프라이버시 장점",
        "온디바이스 AI 개발 가이드",
        "TensorFlow Lite 실전",
        "엣지 AI 산업 활용 사례",
    ],
    "AI 칩 반도체 NVIDIA": [
        "NVIDIA GPU AI 시장 현황",
        "H100 vs A100 vs RTX 성능 비교",
        "AMD vs NVIDIA AI 칩 경쟁",
        "AI 칩 공급망 분석",
        "구글 TPU vs NVIDIA GPU",
        "AI 반도체 투자 전망",
        "개인용 GPU AI 추천",
        "AI 데이터센터 칩 트렌드",
        "한국 AI 반도체 현황",
    ],
    "Transformer 아키텍처": [
        "Transformer 원리 쉽게 이해하기",
        "Attention 메커니즘 완전 설명",
        "GPT vs BERT 구조 비교",
        "Transformer 최신 변형 모델",
        "Vision Transformer(ViT) 분석",
        "Transformer 효율화 기법",
        "Transformer 코드 직접 구현",
        "Transformer가 바꾼 AI 세계",
    ],
    "AI 에이전트 자동화": [
        "AI 에이전트 개념 완전 정리",
        "업무 자동화 AI 에이전트 구축",
        "이메일 자동화 에이전트",
        "데이터 수집 자동화",
        "보고서 자동 생성 에이전트",
        "AI 에이전트 보안 이슈",
        "에이전트 프레임워크 비교",
        "노코드 AI 에이전트 도구",
        "에이전트 실패 사례 분석",
        "AI 에이전트 ROI 측정",
    ],
    "AI 생산성 활용": [
        "AI로 업무 효율 2배 높이기",
        "직장인 AI 도구 모음 추천",
        "글쓰기 AI 도구 비교",
        "회의 요약 AI 완전 가이드",
        "AI로 이메일 자동화",
        "프리랜서 AI 활용 전략",
        "AI 생산성 앱 TOP 10",
        "AI 아침 루틴 만들기",
        "재택근무 AI 도구 추천",
        "팀 협업 AI 도구 활용",
    ],
    "AI 헬스케어 의료": [
        "AI 의료 진단 최신 현황",
        "AI 신약 개발 사례",
        "의료 AI 규제 현황",
        "AI 암 진단 정확도 분석",
        "병원 AI 도입 사례",
        "개인 건강관리 AI 앱",
        "AI 정신건강 서비스",
        "의료 영상 AI 분석",
        "AI 의사 미래 가능성",
        "한국 의료 AI 현황",
    ],
    "AI 교육 에듀테크": [
        "AI 튜터 서비스 비교",
        "Khan Academy AI 활용",
        "학교에서 AI 규제 현황",
        "AI로 맞춤형 학습",
        "AI 작문 도구 교육 활용",
        "대학 AI 도입 사례",
        "AI 영어 회화 앱 추천",
        "학생 AI 활용 윤리",
        "AI 코딩 교육 플랫폼",
        "에듀테크 AI 스타트업",
    ],
    "AI 법률 리걸테크": [
        "AI 법률 서비스 현황",
        "계약서 자동 검토 AI",
        "법률 AI 정확도 분석",
        "변호사 AI 활용 사례",
        "AI 판결 예측 시스템",
        "법률 챗봇 서비스 비교",
        "리걸테크 스타트업 투자 현황",
        "AI 특허 출원 자동화",
        "법률 AI 윤리 문제",
    ],
    "AI 금융 핀테크": [
        "AI 투자 자문 서비스 비교",
        "AI 주식 예측 가능한가",
        "은행 AI 도입 현황",
        "AI 사기 탐지 시스템",
        "AI 신용 평가 모델",
        "알고리즘 트레이딩 AI",
        "AI 개인 재무 관리 앱",
        "핀테크 AI 규제 현황",
        "AI 보험 언더라이팅",
        "한국 금융 AI 현황",
    ],
    "AI 마케팅 광고": [
        "AI 마케팅 도구 완전 비교",
        "AI 광고 카피 작성 실전",
        "SEO AI 도구 활용",
        "AI 개인화 마케팅 전략",
        "소셜미디어 AI 자동화",
        "AI 이메일 마케팅 최적화",
        "광고 크리에이티브 AI 생성",
        "AI A/B 테스트 자동화",
        "AI 마케팅 ROI 분석",
        "콘텐츠 마케팅 AI 워크플로우",
    ],
    "AI 게임 개발": [
        "AI 게임 개발 도구 현황",
        "NPC AI 고도화 사례",
        "Unity AI 기능 활용",
        "AI로 게임 에셋 제작",
        "절차적 생성 AI 기법",
        "게임 테스팅 AI 자동화",
        "AI 게임 시나리오 작성",
        "AI 플레이어 행동 분석",
        "인디 개발자 AI 활용",
    ],
    "AI 음악 작곡": [
        "AI 음악 생성 도구 비교 (Suno/Udio/Stable Audio)",
        "Suno AI로 노래 만들기",
        "AI 작곡 실전 워크플로우",
        "AI 음악 저작권 이슈",
        "음악가 AI 협업 사례",
        "AI 음악 마스터링",
        "유튜브 AI 배경음악 제작",
        "AI 음악의 미래 전망",
    ],
    "AI 영상편집": [
        "AI 영상 편집 도구 비교",
        "Adobe AI 기능 완전 가이드",
        "자동 자막 생성 AI",
        "AI 영상 배경 제거",
        "CapCut AI 기능 활용",
        "유튜브 편집 AI 자동화",
        "AI 썸네일 생성",
        "영상 색보정 AI 도구",
        "AI로 숏폼 영상 제작",
    ],
    "AI 번역 언어": [
        "AI 번역 서비스 비교 (DeepL/Papago/Google)",
        "LLM 번역 품질 분석",
        "전문 분야 AI 번역 정확도",
        "AI 동시통역 현황",
        "번역 AI vs 인간 번역사",
        "다국어 AI 모델 활용",
        "AI 자막 번역 자동화",
        "한국어 특화 AI 번역",
    ],
    "AI 검색엔진": [
        "AI 검색의 미래 분석",
        "Perplexity vs Google SGE 비교",
        "AI 검색이 SEO에 미치는 영향",
        "Microsoft Bing AI 검색 활용",
        "AI 검색 사실 오류 분석",
        "기업용 AI 검색 솔루션",
        "AI 검색 광고 모델 변화",
    ],
    "AI 사이버보안": [
        "AI 해킹 공격 최신 동향",
        "AI 보안 솔루션 비교",
        "딥페이크 탐지 기술",
        "AI 피싱 이메일 대응",
        "LLM 프롬프트 인젝션 공격",
        "AI로 보안 취약점 찾기",
        "제로데이 AI 탐지",
        "기업 AI 보안 가이드라인",
        "AI 신원 확인 기술",
    ],
    "AI 로보틱스 자율주행": [
        "자율주행 AI 최신 현황",
        "Tesla FSD vs 웨이모 비교",
        "국내 자율주행 현황",
        "AI 로봇 최신 동향 (Figure/Optimus)",
        "물류 로봇 AI 활용",
        "드론 AI 자율 비행",
        "AI 로봇 윤리 문제",
        "자율주행 사고 책임 분석",
    ],
    "AI 제조 스마트팩토리": [
        "스마트팩토리 AI 도입 사례",
        "AI 품질 검사 시스템",
        "예측 유지보수 AI",
        "AI 공급망 최적화",
        "제조업 AI 로봇 도입",
        "디지털 트윈 AI 활용",
        "한국 제조업 AI 현황",
    ],
    "AI 농업 푸드테크": [
        "스마트팜 AI 기술 현황",
        "AI 작물 병충해 탐지",
        "드론 농업 AI 활용",
        "AI 수확량 예측",
        "푸드테크 AI 스타트업",
        "AI 식품 안전 검사",
        "수직농장 AI 자동화",
    ],
    "AI 스타트업 투자": [
        "AI 스타트업 투자 현황 분석",
        "2025 AI 유니콘 기업 정리",
        "AI 투자 트렌드 변화",
        "VC들이 주목하는 AI 분야",
        "AI 스타트업 실패 사례 분석",
        "AI 기업 밸류에이션 분석",
        "국내 AI 스타트업 투자 현황",
    ],
    "AI 일자리 취업": [
        "AI가 대체하는 직업 목록",
        "AI 시대 살아남는 직업",
        "AI 엔지니어 취업 가이드",
        "AI 프롬프트 엔지니어 연봉",
        "AI로 이력서/자소서 작성",
        "AI 면접 준비 전략",
        "AI 관련 자격증 추천",
        "비개발자 AI 전환 방법",
        "AI 프리랜서 수익 창출",
    ],
    "AI 윤리 편향": [
        "AI 편향 사례 총정리",
        "AI 성별/인종 편향 분석",
        "공정한 AI 개발 원칙",
        "AI 편향 탐지 방법",
        "AI 윤리 가이드라인 비교",
        "AI 의사결정 투명성",
        "딥페이크 윤리 문제",
        "AI 감시 사회 우려",
    ],
    "AI 저작권 지적재산": [
        "AI 생성물 저작권 현황",
        "AI 학습 데이터 저작권 분쟁",
        "예술가 vs AI 저작권 소송",
        "AI 특허 출원 현황",
        "AI 콘텐츠 상업 이용 가이드",
        "각국 AI 저작권 법률 비교",
        "AI 음악 저작권 사례",
    ],
    "AI 규제 EU AI Act": [
        "EU AI Act 핵심 내용 정리",
        "AI 규제 각국 비교",
        "기업의 AI 규제 대응 방법",
        "AI 고위험 시스템 분류",
        "미국 AI 행정명령 분석",
        "한국 AI 기본법 현황",
        "AI 규제가 혁신에 미치는 영향",
    ],
    "AI 데이터센터 전력": [
        "AI 데이터센터 전력 소비 현황",
        "AI의 탄소 발자국 분석",
        "에너지 효율 AI 칩 동향",
        "AI와 기후변화 딜레마",
        "원자력 + AI 데이터센터 트렌드",
        "녹색 AI 데이터센터 사례",
        "AI 전력 문제 해결책",
    ],
    "오픈소스 vs 클로즈드 AI": [
        "오픈소스 AI 장단점 분석",
        "오픈소스 AI 보안 위험성",
        "기업이 오픈소스 AI 선택하는 이유",
        "오픈소스 AI 최고 모델 비교",
        "Meta 오픈소스 전략 분석",
        "오픈소스 AI 비즈니스 모델",
        "오픈소스 AI 커뮤니티 현황",
    ],
    "AI 구독 서비스 비교": [
        "AI 구독 서비스 완전 비교",
        "ChatGPT Plus vs Claude Pro vs Gemini Advanced",
        "AI 구독 최고 가성비 분석",
        "무료 AI 서비스 총정리",
        "기업용 AI 구독 비교",
        "AI 구독 취소 방법 정리",
        "AI 구독료 인상 분석",
    ],
    "AI PC 노트북 추천": [
        "AI PC 추천 2025 완전 가이드",
        "AI PC vs 일반 PC 차이",
        "로컬 AI에 최적 GPU 추천",
        "AI 작업 최적 노트북",
        "Apple M4 vs Snapdragon X AI",
        "AI PC 구매 체크리스트",
        "예산별 AI PC 추천",
    ],
    "AI 스마트폰 온디바이스": [
        "AI 스마트폰 비교 2025",
        "갤럭시 AI 기능 완전 가이드",
        "Apple Intelligence 분석",
        "온디바이스 AI 프라이버시",
        "AI 스마트폰 생산성 활용",
        "AI 카메라 기능 비교",
        "AI 통역 기능 활용법",
    ],
    "AI 웨어러블": [
        "AI 웨어러블 기기 비교",
        "AI 스마트워치 건강 분석",
        "AI 이어폰 번역 기능",
        "AI 안경 최신 동향",
        "AI 웨어러블 의료 활용",
        "AI 웨어러블 프라이버시",
    ],
    "한국 AI 정책 NIPA": [
        "한국 AI 정책 현황 총정리",
        "NIPA AI 지원 사업 안내",
        "정부 AI 바우처 활용법",
        "한국 AI 전략 분석",
        "공공 AI 도입 사례",
        "AI 인력 양성 정책",
        "한국 AI 경쟁력 분석",
    ],
    "네이버 CLOVA AI": [
        "네이버 CLOVA AI 서비스 정리",
        "HyperCLOVA X 성능 분석",
        "네이버 AI 검색 변화",
        "클로바 노트 완전 활용",
        "네이버 AI vs 카카오 AI 비교",
        "네이버 AI B2B 솔루션",
        "클로바 더빙 활용법",
    ],
    "카카오 AI": [
        "카카오 AI 서비스 총정리",
        "카나나 AI 모델 분석",
        "카카오톡 AI 기능 활용",
        "카카오 AI 전략 방향",
        "카카오 vs 네이버 AI 비교",
        "카카오 AI B2B 현황",
    ],
    "삼성 AI": [
        "삼성 AI 전략 총정리",
        "갤럭시 AI 기능 완전 가이드",
        "삼성 가우스 AI 분석",
        "삼성 AI 반도체 전략",
        "삼성 B2B AI 솔루션",
        "삼성 vs 애플 AI 비교",
    ],
    "SK AI 투자": [
        "SK AI 투자 현황 분석",
        "SK텔레콤 AI 서비스 정리",
        "SK하이닉스 AI 메모리 전략",
        "에이닷 AI 서비스 활용",
        "SK AI 생태계 분석",
    ],
    "KT AI": [
        "KT AI 서비스 총정리",
        "KT 믿음 AI 분석",
        "통신사 AI 전략 비교",
        "KT AI B2B 솔루션",
        "KT AI 인프라 현황",
    ],
    "국내 AI 스타트업": [
        "한국 AI 스타트업 TOP 30",
        "국내 AI 유니콘 현황",
        "투자 받은 AI 스타트업 분석",
        "AI 스타트업 취업 가이드",
        "국내 AI 스타트업 서비스 비교",
        "성공한 AI 스타트업 사례",
        "AI 스타트업 창업 가이드",
    ],
    "Manus AI 에이전트": [
        "Manus AI 완전 분석",
        "Manus vs Devin 비교",
        "완전 자율 AI 에이전트 현황",
        "Manus 실제 사용 후기",
        "AI 에이전트 한계 분석",
        "자율 AI 에이전트 미래",
    ],
    "AI 논문 연구": [
        "이번 주 AI 논문 TOP 5",
        "ICLR/NeurIPS 최신 논문 정리",
        "AI 논문 읽는 방법",
        "arXiv AI 핵심 논문 해설",
        "AI 연구 트렌드 분석",
        "AI 논문 구현 실습",
        "한국 AI 연구 현황",
    ],
    "AI 규제 정책": [
        "글로벌 AI 규제 동향",
        "AI 규제 찬반 논쟁",
        "AI 안전 연구 현황",
        "AI 의식/감정 논쟁",
        "AI 존재론적 위험 분석",
        "AI 정렬 문제란",
        "슈퍼인텔리전스 대비 전략",
    ],
    "오픈소스 AI 모델": [
        "오픈소스 AI 모델 TOP 10",
        "오픈소스 모델 성능 벤치마크",
        "Apache 라이선스 AI 모델",
        "오픈소스 AI 상업 이용 가이드",
        "오픈소스 AI 커뮤니티 동향",
        "오픈소스 AI 파인튜닝 사례",
    ],
    "Phi Microsoft 소형LLM": [
        "Phi 모델 성능 분석",
        "소형 LLM 완전 비교",
        "Phi 로컬 실행 가이드",
        "SLM vs LLM 선택 기준",
        "엣지 디바이스 AI 모델",
        "Microsoft SLM 전략 분석",
    ],
    "Command R Cohere": [
        "Cohere AI 서비스 정리",
        "Command R+ 분석",
        "기업용 AI에 Cohere 쓰는 이유",
        "RAG 특화 Cohere 활용",
        "Cohere API 실전",
        "Cohere vs OpenAI 기업용 비교",
    ],
    "AI 부동산": [
        "부동산 AI 서비스 현황",
        "AI 집값 예측 정확도",
        "AI 임장 리포트 자동화",
        "부동산 AI 챗봇 활용",
        "건축 설계 AI 도구",
        "AI 인테리어 설계",
    ],

    # ── 신규 추가 도메인 앵글 ──────────────────────────────────────────────────

    # AI 모델 추가
    "Phi Microsoft 소형모델": [
        "Phi-3/Phi-4 모델 성능 벤치마크",
        "Phi 소형모델 로컬 실행 가이드",
        "Phi vs Llama 소형모델 비교",
        "엣지 디바이스에서 Phi 실행하기",
        "Microsoft SLM 전략 심층 분석",
        "Phi 파인튜닝 실전 가이드",
    ],
    "Llava 멀티모달": [
        "LLaVA 멀티모달 모델 완전 가이드",
        "LLaVA 로컬 설치 및 실행 방법",
        "LLaVA로 이미지 분석하기 실전",
        "LLaVA vs GPT-4V 성능 비교",
        "LLaVA 파인튜닝으로 맞춤형 비전 AI",
        "오픈소스 멀티모달 AI 모델 비교",
    ],
    "DALL-E 이미지생성": [
        "DALL-E 3 완전 활용 가이드",
        "ChatGPT에서 DALL-E 이미지 생성하기",
        "DALL-E API 연동 실전 튜토리얼",
        "DALL-E 텍스트 포함 이미지 생성 팁",
        "DALL-E vs Midjourney vs Stable Diffusion 비교",
        "DALL-E 상업 목적 이용 가이드",
        "DALL-E inpainting 편집 기능 활용",
    ],
    "Sora OpenAI 영상": [
        "Sora 최신 기능 및 업데이트 정리",
        "Sora 접근 방법 완전 가이드",
        "Sora로 영상 제작 실전 워크플로우",
        "Sora vs Runway vs Kling AI 비교",
        "AI 영상 생성 산업 변화 분석",
        "Sora 프롬프트 최적화 전략",
        "Sora 상업 활용 가능성 분석",
    ],
    "Kling AI 영상생성": [
        "Kling AI 완전 사용 가이드",
        "Kling AI로 영상 만들기 실전",
        "Kling AI vs Sora vs Runway 비교",
        "Kling AI 프롬프트 작성법",
        "중국 AI 영상 생성 기술 현황",
        "Kling AI 무료 사용 방법",
    ],
    "Pika Labs 영상": [
        "Pika Labs 영상 생성 완전 가이드",
        "Pika Labs로 숏폼 영상 만들기",
        "Pika Labs vs Runway Gen-3 비교",
        "Pika Labs 프롬프트 최적화",
        "AI 영상 생성 툴 완전 비교",
        "Pika Labs 무료 플랜 활용법",
    ],
    "Luma Dream Machine": [
        "Luma Dream Machine 완전 가이드",
        "Luma AI로 고품질 영상 만들기",
        "Luma Dream Machine vs Sora 비교",
        "Luma AI 프롬프트 작성 팁",
        "Luma AI 무료 체험 방법",
        "AI 영상 생성 플랫폼 총정리",
    ],

    # AI 개발/인프라
    "Ollama 로컬 LLM": [
        "Ollama 설치 및 기본 사용법",
        "Ollama로 Llama3 로컬 실행하기",
        "Ollama vs LM Studio 비교",
        "Ollama API 서버 구축 가이드",
        "Ollama 모델 다운로드 및 관리",
        "Ollama 성능 최적화 팁",
        "Ollama + Open WebUI 연동하기",
    ],
    "vLLM 추론 최적화": [
        "vLLM 완전 설치 및 사용 가이드",
        "vLLM으로 LLM 추론 속도 높이기",
        "vLLM vs Ollama 성능 비교",
        "vLLM OpenAI 호환 서버 구축",
        "vLLM PagedAttention 원리 설명",
        "프로덕션 LLM 서빙 최적화",
    ],
    "Triton 추론서버": [
        "NVIDIA Triton 추론 서버 설치 가이드",
        "Triton으로 AI 모델 배포하기",
        "Triton vs TensorFlow Serving 비교",
        "Triton 멀티모델 서빙 구축",
        "Triton 성능 최적화 전략",
        "엔터프라이즈 AI 추론 인프라 구축",
    ],
    "LangSmith 모니터링": [
        "LangSmith 완전 활용 가이드",
        "LLM 애플리케이션 모니터링 방법",
        "LangSmith로 프롬프트 디버깅하기",
        "LangSmith 평가 파이프라인 구축",
        "AI 앱 프로덕션 관찰가능성 구축",
        "LangSmith vs 경쟁 도구 비교",
    ],
    "Weights Biases MLOps": [
        "Weights & Biases 완전 가이드",
        "W&B로 ML 실험 추적하기",
        "MLOps 도구 완전 비교",
        "W&B로 모델 성능 시각화",
        "W&B Sweeps 하이퍼파라미터 최적화",
        "ML 모델 배포 파이프라인 구축",
    ],
    "Dify AI 플랫폼": [
        "Dify AI 설치 및 완전 가이드",
        "Dify로 RAG 챗봇 만들기",
        "Dify vs Flowise 비교",
        "Dify 셀프호스팅 배포 방법",
        "Dify로 AI 에이전트 구축하기",
        "노코드 AI 앱 빌더 완전 비교",
    ],
    "Flowise AI 빌더": [
        "Flowise 설치 및 완전 가이드",
        "Flowise로 LLM 앱 만들기",
        "Flowise vs n8n AI 워크플로우 비교",
        "Flowise 셀프호스팅 배포",
        "Flowise로 RAG 시스템 구축",
        "노코드 AI 에이전트 빌더 활용",
    ],
    "CrewAI 멀티에이전트": [
        "CrewAI 설치 및 첫 에이전트 만들기",
        "CrewAI vs AutoGen 비교",
        "CrewAI로 리서치 자동화하기",
        "CrewAI 실전 프로젝트 예시",
        "CrewAI 에이전트 역할 설계 전략",
        "멀티에이전트 시스템 프레임워크 비교",
    ],
    "AutoGen 에이전트": [
        "AutoGen 완전 설치 및 가이드",
        "AutoGen으로 멀티에이전트 구축",
        "AutoGen vs CrewAI 상세 비교",
        "AutoGen 코딩 에이전트 활용",
        "AutoGen 그룹 채팅 에이전트 설계",
        "Microsoft AutoGen 최신 업데이트",
    ],
    "LlamaFactory 파인튜닝": [
        "LlamaFactory 설치 및 사용법",
        "LlamaFactory로 LLM 파인튜닝하기",
        "LlamaFactory vs Unsloth 비교",
        "LlamaFactory 데이터셋 준비 방법",
        "저사양 GPU로 파인튜닝하기",
        "LlamaFactory WebUI 활용 가이드",
    ],

    # AI 응용 확장
    "AI 법률 계약서 검토": [
        "AI 계약서 자동 검토 서비스 비교",
        "AI로 계약서 위험 조항 찾기",
        "법률 AI 도구 실전 활용법",
        "AI 계약 분석 정확도 분석",
        "중소기업 AI 법률 서비스 활용",
        "계약 검토 AI vs 변호사 비교",
    ],
    "AI 세무 회계 자동화": [
        "AI 세무 신고 자동화 방법",
        "AI 회계 소프트웨어 비교",
        "AI로 장부 자동화하기",
        "세금 신고 AI 활용 가이드",
        "프리랜서 AI 세무 관리",
        "AI 세무사 서비스 현황 분석",
    ],
    "AI 의료 영상 진단": [
        "AI 의료 영상 진단 현황 분석",
        "AI X-ray 판독 정확도 분석",
        "AI MRI/CT 영상 분석 기술",
        "의료 영상 AI 규제 현황",
        "병원 AI 영상 진단 도입 사례",
        "AI 진단 vs 의사 진단 비교",
    ],
    "AI 약물 개발": [
        "AI 신약 개발 최신 현황",
        "AI로 단백질 구조 예측하기",
        "AlphaFold 활용 사례",
        "AI 임상시험 최적화",
        "AI 약물 후보 발굴 방법",
        "AI 신약 개발 성공 사례",
    ],
    "AI 기후 환경": [
        "AI 기후변화 대응 최신 현황",
        "AI 탄소 배출 추적 시스템",
        "AI 기후 예측 모델 분석",
        "에너지 효율화 AI 기술",
        "AI 환경 모니터링 활용",
        "AI와 지속가능성 딜레마",
    ],
    "AI 스포츠 분석": [
        "AI 스포츠 데이터 분석 현황",
        "AI 선수 성과 예측 시스템",
        "AI 스포츠 중계 기술",
        "AI 경기 전략 분석 활용",
        "축구/야구 AI 분석 사례",
        "AI 스포츠 베팅 분석",
    ],
    "AI 패션 디자인": [
        "AI 패션 디자인 도구 완전 가이드",
        "AI로 옷 디자인하기 실전",
        "AI 패션 트렌드 예측",
        "AI 가상 피팅룸 서비스",
        "패션 AI 스타트업 현황",
        "AI 맞춤 의류 추천 서비스",
    ],
    "AI 건축 도시계획": [
        "AI 건축 설계 도구 현황",
        "AI 도시 계획 최적화 사례",
        "AI 건물 에너지 효율 분석",
        "AI 인테리어 디자인 도구",
        "BIM + AI 건축 활용",
        "AI 도시 교통 최적화",
    ],
    "AI 물류 공급망": [
        "AI 물류 최적화 현황 분석",
        "AI 공급망 예측 시스템",
        "AI 창고 자동화 로봇",
        "AI 배송 경로 최적화",
        "AI 재고 관리 자동화",
        "AI 물류 스타트업 투자 현황",
    ],
    "AI 금융 리스크": [
        "AI 금융 리스크 관리 현황",
        "AI 신용 리스크 분석 모델",
        "AI 시장 리스크 예측",
        "AI 사기 탐지 고도화 기술",
        "금융 AI 규제 및 컴플라이언스",
        "AI 포트폴리오 리스크 관리",
    ],

    # 국내/아시아 AI
    "일본 AI 정책 기업": [
        "일본 AI 정책 현황 분석",
        "일본 AI 기업 TOP 10",
        "일본 AI 규제 방향 분석",
        "소프트뱅크 AI 투자 현황",
        "일본 AI 스타트업 동향",
        "한일 AI 경쟁력 비교",
    ],
    "중국 AI 규제 현황": [
        "중국 AI 규제 최신 동향",
        "중국 AI 기업 현황 분석",
        "중국 AI vs 미국 AI 경쟁",
        "중국 AI 생성 콘텐츠 규제",
        "중국 AI 수출 통제 분석",
        "바이두/알리바바 AI 전략",
    ],
    "유럽 AI Act 규제": [
        "EU AI Act 핵심 내용 완전 정리",
        "EU AI Act 기업 준수 방법",
        "AI 규제 각국 비교 분석",
        "EU AI Act 고위험 AI 분류",
        "AI Act 시행 일정 및 처벌",
        "유럽 AI 기업 대응 전략",
    ],
    "인도 AI 스타트업": [
        "인도 AI 스타트업 생태계 분석",
        "인도 AI 정부 정책 현황",
        "인도 AI 유니콘 기업 정리",
        "인도 AI 인재 풀 분석",
        "아시아 AI 스타트업 투자 비교",
        "인도 AI 서비스 글로벌 진출",
    ],
    "동남아 AI 시장": [
        "동남아 AI 시장 규모 분석",
        "싱가포르 AI 허브 현황",
        "동남아 AI 스타트업 TOP 10",
        "동남아 AI 정책 비교",
        "동남아 AI 투자 동향",
        "한국 AI 기업 동남아 진출 전략",
    ],
    "SK텔레콤 AI": [
        "SK텔레콤 AI 서비스 총정리",
        "에이닷 AI 서비스 완전 가이드",
        "SKT AI 전략 방향 분석",
        "SKT vs KT AI 경쟁 비교",
        "SKT AI B2B 솔루션 현황",
        "통신사 AI 서비스 비교",
    ],
    "LG AI 연구원": [
        "LG AI 연구원 EXAONE 분석",
        "LG AI 전략 방향",
        "EXAONE 모델 성능 분석",
        "LG 그룹 AI 도입 현황",
        "LG AI B2B 솔루션",
        "국내 대기업 AI 연구소 비교",
    ],
    "현대 AI 모빌리티": [
        "현대차 AI 모빌리티 전략",
        "현대 자율주행 AI 현황",
        "현대 로봇 AI 기술 분석",
        "현대 보스턴다이나믹스 AI",
        "현대 AI 스마트팩토리",
        "국내 자동차 AI 기술 비교",
    ],
}



# ── 도메인 포지셔닝 ───────────────────────────────────────────────────────────
DOMAIN_POSITIONING = {
    # 뉴스성
    "ChatGPT OpenAI":          "뉴스성",
    "Claude Anthropic":        "뉴스성",
    "Gemini Google AI":        "뉴스성",
    "Grok xAI":                "뉴스성",
    "DeepSeek AI 모델":        "뉴스성",
    "Sora OpenAI 영상생성":    "뉴스성",
    "Manus AI 에이전트":       "뉴스성",
    "Perplexity AI":           "뉴스성",
    "Copilot Microsoft AI":    "뉴스성",
    "Llama Meta AI":           "뉴스성",
    "Mistral AI":              "뉴스성",
    "Qwen Alibaba AI":         "뉴스성",

    # 기술심층
    "LLM 언어모델":                    "기술심층",
    "멀티모달 AI":                      "기술심층",
    "AI 코딩 개발":                     "기술심층",
    "프롬프트 엔지니어링":              "기술심층",
    "AI 논문 연구":                     "기술심층",
    "딥러닝 머신러닝":                  "기술심층",
    "RAG 벡터DB":                       "기술심층",
    "파인튜닝 LoRA PEFT":               "기술심층",
    "양자화 GGUF llama.cpp":            "기술심층",
    "컨텍스트 윈도우 LLM":             "기술심층",
    "AI 할루시네이션 해결":             "기술심층",
    "Mixture of Experts MoE":           "기술심층",
    "AI 멀티에이전트 시스템":           "기술심층",
    "컴퓨터 비전 YOLO":                 "기술심층",
    "강화학습 RLHF":                    "기술심층",
    "벡터 데이터베이스 Pinecone Chroma": "기술심층",
    "LangChain LlamaIndex":             "기술심층",
    "Transformer 아키텍처":             "기술심층",
    "HuggingFace 오픈소스":             "기술심층",
    "Phi Microsoft 소형LLM":            "기술심층",
    "Command R Cohere":                 "기술심층",
    "Whisper 음성인식":                 "기술심층",
    "ElevenLabs AI 음성":               "기술심층",
    "Stable Diffusion 이미지생성":      "기술심층",
    "Midjourney AI 아트":               "기술심층",
    "DALL-E OpenAI 이미지":             "기술심층",
    "Runway Gen AI 영상":               "기술심층",
    "AI 칩 반도체 NVIDIA":              "기술심층",
    "엣지 AI 온디바이스":               "기술심층",

    # 산업분석
    "AI 헬스케어 의료":     "산업분석",
    "AI 교육 에듀테크":     "산업분석",
    "AI 법률 리걸테크":     "산업분석",
    "AI 금융 핀테크":       "산업분석",
    "AI 부동산":            "산업분석",
    "AI 마케팅 광고":       "산업분석",
    "AI 게임 개발":         "산업분석",
    "AI 음악 작곡":         "산업분석",
    "AI 영상편집":          "산업분석",
    "AI 번역 언어":         "산업분석",
    "AI 검색엔진":          "산업분석",
    "AI 사이버보안":        "산업분석",
    "AI 로보틱스 자율주행": "산업분석",
    "AI 제조 스마트팩토리": "산업분석",
    "AI 농업 푸드테크":     "산업분석",

    # 실용가이드
    "AI 에이전트 자동화":  "실용가이드",
    "AI 생산성 활용":      "실용가이드",
    "AI 워크플로우 n8n":   "실용가이드",
    "AI API 통합":         "실용가이드",
    "AI PC 노트북 추천":   "실용가이드",
    "AI 스마트폰 온디바이스": "실용가이드",
    "AI 웨어러블":         "실용가이드",
    "AI 구독 서비스 비교": "실용가이드",

    # 트렌드분석
    "AI 스타트업 투자":      "트렌드분석",
    "AI 일자리 취업":        "트렌드분석",
    "AI 윤리 편향":          "트렌드분석",
    "AI 저작권 지적재산":    "트렌드분석",
    "AI 규제 EU AI Act":     "트렌드분석",
    "AI 데이터센터 전력":    "트렌드분석",
    "오픈소스 vs 클로즈드 AI": "트렌드분석",
    "AI 생산성 측정":        "트렌드분석",
    "AI 규제 정책":          "트렌드분석",
    "오픈소스 AI 모델":      "트렌드분석",

    # 국내이슈
    "한국 AI 정책 NIPA": "국내이슈",
    "네이버 CLOVA AI":   "국내이슈",
    "카카오 AI":         "국내이슈",
    "삼성 AI":           "국내이슈",
    "SK AI 투자":        "국내이슈",
    "KT AI":             "국내이슈",
    "국내 AI 스타트업":  "국내이슈",
}



AD_FILTER = {"buy","sale","discount","구매","할인","무료체험","지금신청","click here","subscribe"}

# ── 유틸 ──────────────────────────────────────────────────────────────────────

def get_words(text):
    return set(re.findall(r"[\w가-힣]{2,}", text.lower()))

def get_words_list(text):
    """순서 보존 단어 리스트 (bigram용)"""
    return re.findall(r"[\w가-힣]{2,}", text.lower())

def bigrams(text):
    words = get_words_list(text)  # 순서 보존
    return {(words[i], words[i+1]) for i in range(len(words)-1)}

# 핵심 주제 키워드 그룹 — 같은 그룹 키워드가 양쪽 주제에 겹치면 유사 주제로 판단
TOPIC_KEY_GROUPS = [
    {"claude", "클로드", "anthropic", "앤트로픽"},
    {"chatgpt", "gpt", "openai", "오픈ai"},
    {"gemini", "구글", "google"},
    {"llm", "llama", "라마", "mistral"},
    {"자율주행", "autonomous", "tesla", "테슬라"},
    {"반도체", "gpu", "nvidia", "엔비디아"},
]

def topic_key_overlap(a, b):
    """두 주제가 같은 핵심 키워드 그룹의 단어를 공유하면 True"""
    wa, wb = get_words(a), get_words(b)
    for group in TOPIC_KEY_GROUPS:
        if (group & wa) and (group & wb) and (group & wa) & (group & wb):
            return True
    return False

def similarity(a, b):
    wa, wb = get_words(a), get_words(b)
    ba, bb = bigrams(a), bigrams(b)
    ws = len(wa & wb) / len(wa | wb) if wa and wb else 0.0
    bs = len(ba & bb) / len(ba | bb) if ba and bb else 0.0
    return (ws + bs) / 2.0

def is_duplicate(query, used, threshold=0.30):
    q = query.lower()
    for u in used:
        if similarity(q, u) >= threshold:
            return True
        if len(get_words(q) & get_words(u)) >= 3:
            return True
        if topic_key_overlap(q, u):
            return True
    # 코사인 유사도 추가 검증
    if is_duplicate_cosine(query, used, threshold=0.35):
        return True
    return False

def tfidf_vector(text, corpus):
    """간단한 TF-IDF 코사인 유사도용 벡터 (외부 라이브러리 없이)"""
    words = get_words_list(text)
    tf = {}
    for w in words:
        tf[w] = tf.get(w, 0) + 1
    total = len(words) or 1
    # IDF: 전체 corpus 중 몇 문서에 등장하는지
    idf = {}
    N = len(corpus) + 1
    for w in tf:
        df = sum(1 for doc in corpus if w in get_words(doc)) + 1
        idf[w] = math.log(N / df)
    return {w: (c / total) * idf[w] for w, c in tf.items()}

def cosine_similarity(a, b, corpus):
    """두 텍스트의 TF-IDF 코사인 유사도"""
    va = tfidf_vector(a, corpus)
    vb = tfidf_vector(b, corpus)
    keys = set(va) | set(vb)
    dot = sum(va.get(k, 0) * vb.get(k, 0) for k in keys)
    na = math.sqrt(sum(v**2 for v in va.values())) or 1e-9
    nb = math.sqrt(sum(v**2 for v in vb.values())) or 1e-9
    return dot / (na * nb)

def is_duplicate_cosine(query, used, threshold=0.35):
    """코사인 유사도 기반 중복 체크"""
    if not used:
        return False
    corpus = list(used) + [query]
    q = query.lower()
    for u in used:
        if cosine_similarity(q, u.lower(), corpus) >= threshold:
            return True
    return False

def has_ad(text):
    tl = text.lower()
    return any(w in tl for w in AD_FILTER)

# ── 이력 로드 ─────────────────────────────────────────────────────────────────

def load_posted_history():
    used = set()
    posts_dir = os.path.join(BASE, "posts")
    if not os.path.isdir(posts_dir):
        return used
    for fn in os.listdir(posts_dir):
        if not fn.endswith(".md"):
            continue
        try:
            for line in open(os.path.join(posts_dir, fn), encoding="utf-8"):
                line = line.strip()
                if line.startswith("title:"):
                    title = line[6:].strip().strip('"\'')
                    if title:
                        used.add(title.lower())
                    break
        except Exception:
            pass
    print(f"  [중복방지] 이력 {len(used)}개 로드")
    return used

# ── 주간 앵글 파일 로드 ───────────────────────────────────────────────────────

def load_weekly_angles():
    angles_dir = os.path.join(BASE, "output", "angles")
    for delta in [0, 7, 14]:
        target = datetime.date.today() - datetime.timedelta(days=delta)
        yw     = target.strftime("%Y-W%V")
        path   = os.path.join(angles_dir, f"topic_angles_{yw}.json")
        if os.path.exists(path):
            try:
                data   = json.load(open(path, encoding="utf-8"))
                angles = data.get("angles", {})
                if angles:
                    print(f"  [앵글] 주간 파일 로드: {yw} ({data.get('total_angles',0)}개)")
                    return angles
            except Exception:
                pass
    print("  [앵글] 주간 파일 없음 → TOPIC_SUBTYPES 사용")
    return TOPIC_SUBTYPES

# ── 도메인 로테이션 ───────────────────────────────────────────────────────────

def get_todays_domains():
    seed    = int(hashlib.md5(TODAY.encode()).hexdigest(), 16) % len(AI_DOMAINS)
    rotated = AI_DOMAINS[seed:] + AI_DOMAINS[:seed]
    return rotated[:DAILY_DOMAINS_COUNT]

# ── HTTP / 스크래핑 유틸 ──────────────────────────────────────────────────────

def http_get_json(url, headers=None, timeout=12):
    h = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))

def scrapling_fetch(url):
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        tmp = f.name
    try:
        subprocess.run(
            ["scrapling", "extract", "get", url, tmp, "--impersonate", "chrome", "--no-verify"],
            capture_output=True, text=True, timeout=30
        )
        with open(tmp, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        print(f"  ⚠️  scrapling: {e}")
        return ""
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass

def fetch_hackernews(query, max_results=5):
    try:
        q   = urllib.parse.quote(query)
        url = (f"https://hn.algolia.com/api/v1/search"
               f"?query={q}&tags=story&numericFilters=points>5&hitsPerPage={max_results}")
        data = http_get_json(url, timeout=8)
        return [{"title": h.get("title", ""), "source": "hn"}
                for h in data.get("hits", []) if h.get("title")]
    except Exception:
        return []

def fetch_brave_search(query, count=8):
    if not BRAVE_API_KEY:
        return []
    try:
        url  = (f"https://api.search.brave.com/res/v1/web/search"
                f"?q={urllib.parse.quote(query)}&count={count}&search_lang=ko&freshness=pw")
        data = http_get_json(url, headers={"X-Subscription-Token": BRAVE_API_KEY})
        return [{"title": r.get("title", ""), "source": "brave"}
                for r in data.get("web", {}).get("results", []) if r.get("title")]
    except Exception:
        return []

# ── 뉴스 파싱 (기존 scrapling 방식 유지) ─────────────────────────────────────

def parse_google_news(content, source):
    items   = []
    pattern = re.compile(r'<a href="[^"]*" target="_blank">(.*?)</a>', re.DOTALL)
    for m in pattern.finditer(content):
        title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if len(title) >= 15:
            items.append({"title": title, "source": source})
        if len(items) >= 10:
            break
    return items

def parse_reddit_rss(content, source):
    items = []
    for line in content.splitlines():
        line  = line.strip()
        title = re.sub(r'<[^>]+>', '', line).strip()
        if len(title) > 20 and not title.startswith("http") and "://" not in title:
            items.append({"title": title, "source": source})
        if len(items) >= 7:
            break
    return items

def fetch_x_fxtwitter():
    accounts = ["sama", "AnthropicAI", "OpenAI", "GoogleDeepMind",
                "karpathy", "deepseek_ai", "MistralAI"]
    items = []
    for account in accounts:
        content = scrapling_fetch(f"https://api.fxtwitter.com/{account}")
        if not content or "404" in content[:50]:
            continue
        for text in re.findall(r'"text"\s*:\s*"([^"]{30,200})"', content)[:2]:
            text = text.replace("\\n", " ").strip()
            kws  = ["ai", "model", "llm", "gpt", "claude", "gemini"]
            if any(kw in text.lower() for kw in kws):
                items.append({"title": f"[X/@{account}] {text[:100]}", "source": f"X/@{account}"})
        if len(items) >= 6:
            break
    return items

def fetch_all_news():
    all_news = []

    print("  📡 Google News (EN) 수집 중...")
    url   = "https://news.google.com/rss/search?q=AI+LLM+Claude+GPT+Gemini+when:7d&hl=en-US&gl=US&ceid=US:en"
    items = parse_google_news(scrapling_fetch(url), "Google News EN")
    all_news.extend(items); print(f"     → {len(items)}개")

    print("  📡 Google News (KO) 수집 중...")
    url   = "https://news.google.com/rss/search?q=AI+인공지능+ChatGPT+Claude+when:30d&hl=ko&gl=KR&ceid=KR:ko"
    items = parse_google_news(scrapling_fetch(url), "Google News KO")
    all_news.extend(items); print(f"     → {len(items)}개")

    for rurl, name in [
        ("https://www.reddit.com/r/artificial/top/.rss?t=week",      "r/artificial"),
        ("https://www.reddit.com/r/MachineLearning/top/.rss?t=week", "r/MachineLearning"),
        ("https://www.reddit.com/r/LocalLLaMA/top/.rss?t=week",      "r/LocalLLaMA"),
    ]:
        print(f"  📡 {name} 수집 중...")
        items = parse_reddit_rss(scrapling_fetch(rurl), name)
        all_news.extend(items); print(f"     → {len(items)}개")

    print("  📡 X(Twitter) 수집 중...")
    items = fetch_x_fxtwitter()
    all_news.extend(items); print(f"     → {len(items)}개")

    print("  📡 HackerNews 수집 중...")
    items = fetch_hackernews("AI LLM language model")
    all_news.extend(items); print(f"     → {len(items)}개")

    if BRAVE_API_KEY:
        print("  📡 Brave Search 수집 중...")
        items = fetch_brave_search("AI 최신 소식 2026")
        all_news.extend(items); print(f"     → {len(items)}개")

    return all_news

# ── 도메인 기반 앵글 쿼리 생성 ───────────────────────────────────────────────

def generate_domain_queries(used_history):
    weekly_angles  = load_weekly_angles()
    todays_domains = get_todays_domains()
    queries = []
    for domain in todays_domains:
        subtypes = weekly_angles.get(domain, TOPIC_SUBTYPES.get(domain, []))
        if subtypes:
            seed_val = int(hashlib.md5((TODAY + domain).encode()).hexdigest(), 16)
            angle    = subtypes[seed_val % len(subtypes)]
            query    = f"{domain} {angle}"
        else:
            angle = ""
            query = domain
        if not is_duplicate(query, used_history):
            queries.append({"title": query, "source": f"domain:{domain}",
                            "domain": domain, "angle": angle})
    return queries

def expand_domains(used_history, needed):
    import random as _rnd
    used_today = set(get_todays_domains())
    unused     = [d for d in AI_DOMAINS if d not in used_today]
    rng        = _rnd.Random(int(hashlib.md5((TODAY + "expand").encode()).hexdigest(), 16))
    rng.shuffle(unused)
    weekly_angles = load_weekly_angles()
    extra = []
    for domain in unused:
        if len(extra) >= needed:
            break
        subtypes = weekly_angles.get(domain, TOPIC_SUBTYPES.get(domain, []))
        if subtypes:
            seed_val = int(hashlib.md5((TODAY + domain + "ext").encode()).hexdigest(), 16)
            angle    = subtypes[seed_val % len(subtypes)]
            query    = f"{domain} {angle}"
        else:
            angle = ""
            query = domain
        if not is_duplicate(query, used_history):
            extra.append({"title": query, "source": f"expanded:{domain}",
                          "domain": domain, "angle": angle})
    return extra

# ── 최적 주제 선정 (Claude) ───────────────────────────────────────────────────

def select_best_topic(news_items, used_history):
    today_str     = datetime.date.today().strftime("%Y년 %m월 %d일")
    domain_queries = generate_domain_queries(used_history)

    seen   = set()
    merged = []
    for item in news_items + domain_queries:
        t = item.get("title", "")
        if t and t not in seen and not has_ad(t) and not is_duplicate(t, used_history):
            seen.add(t)
            merged.append(item)

    if len(merged) < 5:
        extra = expand_domains(used_history, 10 - len(merged))
        for item in extra:
            t = item.get("title", "")
            if t and t not in seen:
                seen.add(t)
                merged.append(item)

    if not merged:
        return {"topic": "AI 최신 트렌드 2026", "keywords": ["AI", "트렌드", "2026"],
                "angle": "트렌드분석", "reason": "fallback", "source_news": ""}

    news_text = "\n".join([
        f"[{item['source']}] {item['title']}"
        for item in merged[:35]
    ])

    # 기존 발행 제목 목록을 프롬프트에 주입
    used_titles_text = "\n".join(f"- {t}" for t in sorted(used_history)) if used_history else "없음"

    prompt = f"""오늘은 {today_str}입니다.

아래는 수집한 최신 AI/기술 뉴스 및 주제 후보입니다.

[주제 후보]
{news_text}

[이미 발행된 포스트 제목 — 절대 중복 금지]
{used_titles_text}

AI키퍼 블로그(한국어 AI 전문)에 가장 적합한 주제 1개를 선정해주세요.

요구사항:
1. 위 목록 기반의 실제 소식/주제
2. 이미 발행된 포스트와 주제·키워드가 겹치지 않는 완전히 새로운 주제 (같은 제품/기업이라도 각도가 완전히 다르면 허용)
3. 단순 뉴스 요약 X → "왜 중요한가", "어떻게 활용하나" 각도
4. 한국 독자가 궁금해할 주제 (실용적, 구체적)

형식:
===TOPIC===
블로그 주제 (한국어, 구체적으로)
===KEYWORDS===
키워드1,키워드2,키워드3,키워드4
===REASON===
선택 이유
===ANGLE===
차별화된 글쓰기 각도
===SOURCE_NEWS===
참고한 원본 후보 제목
===END==="""

    _ck = dict(base_url=ANTHROPIC_BASE_URL, timeout=120, max_retries=2)
    if ANTHROPIC_API_KEY:
        _ck["api_key"] = ANTHROPIC_API_KEY
    client = _anthropic.Anthropic(**_ck)
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text

    def extract(t, key):
        tags = ["===TOPIC===","===KEYWORDS===","===REASON===","===ANGLE===","===SOURCE_NEWS===","===END==="]
        tag  = f"==={key}==="
        s    = t.find(tag)
        if s == -1:
            return ""
        s += len(tag)
        e  = len(t)
        for other in tags:
            if other == tag:
                continue
            pos = t.find(other, s)
            if 0 < pos < e:
                e = pos
        return t[s:e].strip()

    return {
        "topic":       extract(text, "TOPIC"),
        "keywords":    [k.strip() for k in extract(text, "KEYWORDS").split(",") if k.strip()],
        "reason":      extract(text, "REASON"),
        "angle":       extract(text, "ANGLE"),
        "source_news": extract(text, "SOURCE_NEWS"),
    }


if __name__ == "__main__":
    print(f"🔍 AI키퍼 주제 발굴 v3 — {TODAY}")

    used_history = load_posted_history()

    print("\n📡 뉴스 수집 중...")
    news = fetch_all_news()
    print(f"\n✅ 총 {len(news)}개 수집 완료")

    if len(news) < 2:
        print("TOPIC:2026년 AI 최신 트렌드 — Claude·GPT·Gemini 무엇이 달라졌나")
        print("KEYWORDS:AI트렌드,Claude,GPT,Gemini,2026")
        print("ANGLE:실제 사용자 관점의 비교 분석")
        sys.exit(0)

    print("\n🤖 최적 주제 선정 중 (Claude)...")
    result = select_best_topic(news, used_history)

    print(f"\n📌 선정된 주제: {result['topic']}")
    print(f"   키워드: {', '.join(result['keywords'])}")
    print(f"   이유: {result['reason']}")

    print(f"\nTOPIC:{result['topic']}")
    print(f"KEYWORDS:{','.join(result['keywords'])}")
    print(f"ANGLE:{result['angle']}")
