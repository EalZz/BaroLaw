# MainActivity 모듈화 및 TTS 개선 플랜

> 상태: Draft  
> 기준일: 2026-04-27  
> 대상 모듈: `D:/BaroLaw/frontend/app`  
> 비대상: `backend` RAG 검색, corpus, prompt, reranker, preprocessor

## 목표

현재 `MainActivity.kt`에 모여 있는 채팅 상태 관리, 스트리밍 제어, TTS/STT, Compose UI를 작은 파일로 분리한다. 기능 동작은 유지하면서 이후 TTS 품질 개선과 세션/스트리밍 유지보수를 쉽게 만든다.

이번 작업은 Android 프론트 구조 정리를 우선한다. 서버 RAG 시스템은 수정하지 않는다.

## 현재 판단

- 현재 TTS는 Android 기본 `TextToSpeech` 엔진을 사용한다.
- `MainActivity.kt`에서 `tts = TextToSpeech(this, this)`, `tts.language = Locale.KOREAN`, `tts.speak(...)`로 직접 제어한다.
- 음성 품질은 앱 코드보다 사용자 기기에 설치된 TTS 엔진과 선택된 voice 품질에 크게 좌우된다.
- `MainActivity.kt`는 약 53KB이며 다음 책임이 섞여 있다.
  - 세션 목록 및 현재 세션 상태
  - 메시지 추가 및 로딩 애니메이션
  - SSE 스트리밍 수신 및 정지
  - TTS, STT 제어
  - Compose 화면 구성
  - 메시지 버블 및 법령 상세 표시

## 리팩터링 원칙

- 기능 동작을 바꾸지 않는다.
- 한 번에 큰 구조 변경을 하지 않고, 컴파일 가능한 작은 단위로 분리한다.
- 각 task 완료 후 `:app:compileDebugKotlin`을 실행한다.
- RAG/backend 파일은 건드리지 않는다.
- 먼저 파일 분리만 하고, ViewModel 도입은 마지막 단계에서 결정한다.
- TTS 서버 교체는 이번 1차 리팩터링 범위에 넣지 않는다. 단, 나중에 교체 가능하도록 `SpeechController` 경계를 만든다.

## 권장 작업 순서

### Task 1. 모델 분리

**목표:** `ChatMessage`, `ChatSession`을 `MainActivity.kt`에서 분리한다.

**파일:**
- 생성: `frontend/app/src/main/java/com/example/barolaw/model/ChatModels.kt`
- 수정: `frontend/app/src/main/java/com/example/barolaw/MainActivity.kt`
- 수정 가능: `frontend/app/src/main/java/com/example/barolaw/ChatStreamManager.kt`

**작업:**
- `ChatMessage`, `ChatSession` data class를 새 파일로 이동한다.
- 필요한 import를 정리한다.
- 동작 변경 없이 컴파일만 확인한다.

**검증:**
```powershell
Set-Location D:\BaroLaw\frontend
.\gradlew.bat :app:compileDebugKotlin
```

**주의:**
- `mutableStateListOf()`를 사용하는 `ChatSession.messages` 동작이 바뀌면 안 된다.
- 메시지 ID 기본값 `UUID.randomUUID().toString()`도 그대로 유지한다.

---

### Task 2. SpeechController 분리

**목표:** TTS/STT 제어를 `MainActivity.kt`에서 분리한다.

**파일:**
- 생성: `frontend/app/src/main/java/com/example/barolaw/speech/SpeechController.kt`
- 수정: `frontend/app/src/main/java/com/example/barolaw/MainActivity.kt`

**작업:**
- `TextToSpeech`, `SpeechRecognizer`, `lastSpokenText`, `isListening` 관련 로직을 `SpeechController`로 이동한다.
- `MainActivity`는 다음 수준의 메서드만 호출한다.
  - `speechController.toggleSpeech(text)`
  - `speechController.stopSpeech()`
  - `speechController.startListening(onResult)`
  - `speechController.stopListening()`
  - `speechController.release()`
- 기존 TTS 정지 동작은 유지한다.
- 기존 STT 결과가 `sendMessage(matches[0])`로 이어지는 흐름을 유지한다.

**검증:**
```powershell
Set-Location D:\BaroLaw\frontend
.\gradlew.bat :app:compileDebugKotlin
```

**수동 테스트:**
- AI 답변의 음성 버튼을 누르면 읽기 시작한다.
- 읽는 중 같은 음성 버튼을 누르면 정지한다.
- 마이크 입력 후 메시지 전송이 기존처럼 동작한다.
- 생성 정지 버튼을 눌렀을 때 TTS/STT도 같이 멈춘다.

**주의:**
- 이 단계에서는 더 자연스러운 외부 TTS를 도입하지 않는다.
- Android 기본 TTS 동작만 보존한다.

---

### Task 3. 기본 TTS 튜닝 추가

**목표:** Android 기본 TTS 안에서 가능한 자연스러움 개선을 먼저 적용한다.

**파일:**
- 수정: `frontend/app/src/main/java/com/example/barolaw/speech/SpeechController.kt`

**작업:**
- `TextToSpeech.SUCCESS` 이후 다음 옵션을 검토해 적용한다.
  - `language = Locale.KOREAN`
  - `setSpeechRate(0.92f ~ 1.0f)`
  - `setPitch(0.95f ~ 1.05f)`
  - 사용 가능한 한국어 voice 중 network voice 또는 quality가 높은 voice 우선 선택
- voice 선택 실패 시 기존 기본 한국어 TTS로 fallback한다.

**검증:**
```powershell
Set-Location D:\BaroLaw\frontend
.\gradlew.bat :app:compileDebugKotlin
```

**수동 테스트:**
- 실제 기기 또는 에뮬레이터에서 한국어 답변을 재생한다.
- 너무 느리거나 어색하면 rate/pitch 값을 되돌린다.

**주의:**
- 기기마다 사용 가능한 voice 목록이 다를 수 있으므로 voice 선택 실패는 정상 fallback으로 처리한다.
- 여기서 음성 품질 개선 폭은 제한적이다.

---

### Task 4. Compose UI 파일 분리

**목표:** 화면 표시용 Composable을 `MainActivity.kt`에서 분리한다.

**파일:**
- 생성: `frontend/app/src/main/java/com/example/barolaw/ui/ChatScreen.kt`
- 생성: `frontend/app/src/main/java/com/example/barolaw/ui/MessageBubble.kt`
- 생성: `frontend/app/src/main/java/com/example/barolaw/ui/SettingsScreen.kt`
- 수정: `frontend/app/src/main/java/com/example/barolaw/MainActivity.kt`

**작업:**
- `ChatScreen`을 `ui/ChatScreen.kt`로 이동한다.
- 메시지 버블 관련 Composable을 `ui/MessageBubble.kt`로 이동한다.
- `SettingsScreen`을 `ui/SettingsScreen.kt`로 이동한다.
- `MainActivity`는 상태와 콜백을 UI에 넘기는 역할만 하도록 줄인다.

**검증:**
```powershell
Set-Location D:\BaroLaw\frontend
.\gradlew.bat :app:compileDebugKotlin
```

**수동 테스트:**
- 메인 화면 진입
- 새 질문 전송
- 세션 목록 열기/닫기
- 기존 세션 선택
- 메시지 법령 상세 보기
- 음성 버튼 동작
- 정지 버튼 동작

**주의:**
- UI 이동 중 import가 크게 늘어날 수 있으므로 한 파일씩 분리한다.
- Material/Compose import 정리는 컴파일 에러 기준으로 최소 수정한다.

---

### Task 5. 채팅 상태 관리 분리 검토

**목표:** `sendMessage`, `stopGeneration`, `loadHistory`, 로딩 애니메이션 관리가 ViewModel 또는 controller로 갈 수 있는지 판단한다.

**파일 후보:**
- 생성 후보: `frontend/app/src/main/java/com/example/barolaw/chat/ChatStateController.kt`
- 또는 생성 후보: `frontend/app/src/main/java/com/example/barolaw/chat/ChatViewModel.kt`
- 수정: `frontend/app/src/main/java/com/example/barolaw/MainActivity.kt`

**선택지 A: Controller 유지**
- 장점: 현재 구조와 가깝고 변경량이 작다.
- 단점: lifecycle, coroutine scope 관리가 계속 Activity에 남을 수 있다.

**선택지 B: ViewModel 도입**
- 장점: 상태 관리와 UI lifecycle 분리가 명확해진다.
- 단점: 변경 범위가 커지고 기존 Compose 상태와 충돌 가능성이 있다.

**권장:** Task 1~4 완료 후 파일 크기와 안정성을 보고 결정한다. 지금은 ViewModel 도입을 확정하지 않는다.

---

### Task 6. 고품질 TTS 교체 설계

**목표:** 더 자연스러운 TTS를 위한 서버 기반 TTS 도입 여부를 결정한다.

**선택지 A. Android 기본 TTS 유지**
- 장점: 무료, 오프라인 가능, 서버 변경 없음.
- 단점: 자연스러움 한계가 크고 기기별 편차가 있다.

**선택지 B. 서버에서 TTS 생성 후 앱에서 재생**
- 후보: OpenAI TTS, Google Cloud TTS, Naver CLOVA Voice, Azure Neural TTS
- 장점: 훨씬 자연스러운 음성 품질.
- 단점: 비용, 지연시간, API 키 보안, 캐싱 설계 필요.

**선택지 C. 하이브리드**
- 기본은 Android TTS.
- 설정에서 고품질 음성 사용 옵션을 켜면 서버 TTS 사용.
- 장점: MVP 안정성과 품질 개선을 동시에 가져갈 수 있다.
- 단점: 구현 복잡도가 가장 높다.

**권장:** 당장은 선택지 A를 튜닝하고, 이후 선택지 C를 목표 구조로 둔다. `SpeechController`를 먼저 분리하면 나중에 서버 TTS로 바꾸기 쉽다.

## 완료 기준

- `MainActivity.kt`가 눈에 띄게 작아지고, 주요 책임이 파일 단위로 분리된다.
- 기존 채팅, 세션, 스트리밍 정지, TTS, STT 동작이 유지된다.
- 각 task마다 `:app:compileDebugKotlin`이 통과한다.
- backend RAG 관련 파일은 수정되지 않는다.

## 권장 커밋 단위

1. `refactor: extract chat models`
2. `refactor: extract speech controller`
3. `feat: tune android tts voice settings`
4. `refactor: split compose chat ui`
5. `docs: document high quality tts options`

## 보류 항목

- 서버 기반 TTS 실제 도입
- 회원가입/로그인/UID 관리
- RAG 검색 최적화
- corpus, BM25, embedding, reranker 변경
- 대규모 ViewModel 전환

