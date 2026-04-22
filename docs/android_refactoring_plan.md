# Android App Refactoring Plan

> Status: Draft  
> 기준일: 2026-04-22  
> 기준 모듈: `D:/BaroLaw/frontend/app`  
> 비대상 모듈: `D:/BaroLaw/android/app`은 현재 백업/비활성 사본으로 취급한다.

## 목표

현재 실제 Android 프론트로 사용할 `app` 모듈을 기준으로, 기능 동작은 유지하면서 `MainActivity.kt`와 `ChatStreamManager.kt`의 책임을 단계적으로 분리한다.

1차 리팩터링은 Android 앱 내부를 우선 변경한다. RAG 검색/랭킹/프롬프트 최적화 시스템은 수정하지 않는다.

다만 현재 `LEGAL_*` 문자열 태그 전달 방식이 Android 파싱 안정성에 직접 영향을 주므로, 별도 후속 작업으로 `backend/app.py`의 SSE 응답 조립/전송 포맷만 제한적으로 다룰 수 있다. 이 후속 작업은 이미 계산된 `rag_results`와 `context_data`를 앱에 포장해 보내는 레이어에 한정하며, RAG 결과 생성 방식은 변경하지 않는다.

## 현재 판단

- `D:/BaroLaw/frontend/app`을 실제 Android 앱 모듈로 확정한다.
- `D:/BaroLaw/android/app`은 동일하거나 유사한 Android 코드가 있는 사본이므로, 이번 리팩터링 대상에서 제외한다.
- GitHub 최신 `main` 기준으로도 루트 `app`과 `android/app`이 모두 존재한다.
- 루트 `app/MainActivity.kt`에는 `streamManager` 선언이 있고, `android/app/MainActivity.kt`보다 정상 빌드 가능성이 높다.

## 주요 문제

### 1. `MainActivity.kt` 책임 과다

`frontend/app/src/main/java/com/example/barolaw/MainActivity.kt`가 다음 책임을 한 파일에서 모두 처리한다.

- Compose 화면 구성
- 세션 목록 및 현재 세션 상태
- 메시지 추가 및 로딩 애니메이션
- SSE 스트리밍 응답 누적
- `LEGAL_DETAILS`, `LEGAL_BASIS`, `ASSISTANT_ANSWER` 파싱
- 법령 상세 팝업 상태
- 음성 인식
- TTS 출력

이 구조는 새 기능 추가 시 회귀 위험이 크고, 파싱 버그와 UI 버그를 분리해서 테스트하기 어렵다.

### 2. 문자열 태그 기반 SSE 파싱

백엔드는 응답 텍스트에 다음 태그를 섞어 보낸다.

- `---[LEGAL_BASIS]---`
- `---[LEGAL_DETAILS]---`
- `---[RAG_METADATA]---`
- `---[RAG_ENGINE_RESULT]---`
- `---[ASSISTANT_ANSWER]---`

Android 앱은 이 태그를 `substringAfter`, `substringBefore`, `lastIndexOf(']')` 등으로 파싱한다. 이 방식은 스트리밍 중 JSON이 덜 도착했거나, 본문에 유사 문자열이 들어간 경우 취약하다.

### 3. `ChatStreamManager.kt`의 역할 혼재

`ChatStreamManager.kt`는 네트워크 클라이언트, URL 조립, SSE 라인 처리, JSON payload 파싱, 세션 API 호출을 함께 담당한다.

1차 리팩터링에서는 큰 구조 개편 없이 URL 구성과 SSE 응답 처리만 명확히 분리한다.

## 리팩터링 원칙

- 기능 동작을 바꾸지 않는다.
- `D:/BaroLaw/frontend/app`만 수정한다.
- `D:/BaroLaw/android/app`은 이번 단계에서 수정하지 않는다.
- RAG 검색, reranker, preprocessor, prompt, corpus, 평가셋 관련 파일은 수정하지 않는다.
- `backend/app.py`는 후속 응답 포맷 안정화 작업에서만 제한적으로 수정할 수 있다.
- 파일 분리는 작게 시작한다.
- 파싱 로직은 테스트 가능한 순수 함수로 만든다.

## 1차 범위

### 포함

- `MainActivity.kt`에서 법령 상세 및 본문/근거 파싱 로직 분리
- `ChatBubble()` 내부 표시용 파싱을 공용 parser로 통일
- `sendMessage()` 내부 중복 `LEGAL_DETAILS` JSON 파싱 제거
- `ChatStreamManager.kt`의 채팅 스트림 URL 구성 분리
- 사용하지 않는 GET 요청 body 관련 코드 제거 검토

### 제외

- ViewModel 도입
- Compose UI 파일 대규모 분리
- RAG 시스템 관련 파일 변경
- `BASE_URL`을 Gradle `BuildConfig`로 이동
- 루트 `app`과 `android/app` 폴더 정리 또는 삭제

## 변경 허용 및 금지 범위

### 허용 범위

이번 리팩터링의 주 대상은 Android 앱이다.

- `frontend/app/src/main/java/com/example/barolaw/LegalResponseParser.kt`
- `frontend/app/src/test/java/com/example/barolaw/LegalResponseParserTest.kt`
- `frontend/app/src/main/java/com/example/barolaw/MainActivity.kt`
- `frontend/app/src/main/java/com/example/barolaw/ChatStreamManager.kt`

후속 응답 포맷 안정화 작업에서는 아래 범위만 제한적으로 허용한다.

- `backend/app.py`의 SSE payload 생성 및 전송 조립부
- 대상 함수/블록 후보:
  - `build_sse_payload`
  - `generate_ai_stream`
  - `LEGAL_BASIS` / `LEGAL_DETAILS` / `RAG_ENGINE_RESULT` / `RAG_METADATA` 조립부

허용되는 변경은 이미 계산된 `context_data["rag_results"]`, `context_data["rag_context"]`, `perf_meta` 등을 구조화해 앱에 전달하는 작업에 한정한다.

### 변경 금지 범위

이번 리팩터링에서는 다음 파일과 디렉터리를 수정하지 않는다.

- `backend/rag.py`
- `backend/rag_config.yaml`
- `backend/preprocessor.py`
- `backend/prompts.py`
- `backend/legal_synonyms.py`
- `backend/autorag_data/`
- `autorag_eval/`
- `tests/golden_dataset.json`
- RAG 성능 평가, corpus, retrieval, reranker, prompt tuning 관련 파일

검색 결과 생성 방식, RAG metadata 계산 방식, prompt 구성, preprocessor 결과, rerank/boost/sniper/keyword/category 처리 방식은 변경하지 않는다.

## 파일 계획

### 생성

`frontend/app/src/main/java/com/example/barolaw/LegalResponseParser.kt`

책임:

- 누적 응답 문자열에서 `LawDetail` 목록 추출
- 채팅 본문 표시 문자열 추출
- 법적 근거 표시 문자열 추출
- 법적 근거 bullet 목록 추출
- 파싱 실패 시 예외를 밖으로 던지지 않고 빈 결과 반환

예상 API:

```kotlin
object LegalResponseParser {
    const val DETAILS_TAG = "---[LEGAL_DETAILS]---"
    const val BASIS_TAG = "---[LEGAL_BASIS]---"
    const val ANSWER_TAG = "---[ASSISTANT_ANSWER]---"

    fun extractLawDetails(content: String): List<LawDetail>

    fun extractDisplaySections(content: String): LegalDisplaySections
}

data class LegalDisplaySections(
    val mainBody: String,
    val legalBasis: String,
    val legalBasisItems: List<String>
)
```

`LawDetail`은 현재 `MainActivity.kt`에 정의되어 있다. 1차에서는 이동하지 않고 같은 패키지의 타입으로 참조한다.

### 수정

`frontend/app/src/main/java/com/example/barolaw/MainActivity.kt`

수정 내용:

- `sendMessage()` 안의 스트리밍 중 `LEGAL_DETAILS` 파싱을 `LegalResponseParser.extractLawDetails(fullResponse)`로 교체한다.
- `sendMessage()` 완료 시점의 중복 JSON 파싱도 같은 함수로 교체한다.
- `ChatBubble()` 안의 `actualLawDetails` 계산과 본문/근거 분리를 `LegalResponseParser`로 교체한다.
- 기존 UI 렌더링 구조는 유지한다.

`frontend/app/src/main/java/com/example/barolaw/ChatStreamManager.kt`

수정 내용:

- `buildChatStreamUrl(...)` private 함수를 추가한다.
- `ngrok-skip-browser-warning` 헤더 추가를 반복하지 않도록 작은 helper를 검토한다.
- `fetchChatStream()`의 사용하지 않는 `json` 및 `requestBody` 변수를 제거한다.
- 세션 API 함수의 동작은 변경하지 않는다.

## 상세 작업 체크리스트

### Task 1. Parser 파일 생성

- [ ] `LegalResponseParser.kt` 생성
- [ ] 태그 상수를 parser로 이동
- [ ] `extractLawDetails(content: String)` 구현
- [ ] `extractDisplaySections(content: String)` 구현
- [ ] JSON 파싱 실패 시 빈 리스트 반환
- [ ] 본문/근거 분리 규칙을 현재 `ChatBubble()` 동작과 맞춘다.

완료 기준:

- 태그 문자열이 parser에 모인다.
- 파싱 실패가 앱 크래시로 이어지지 않는다.

### Task 2. `sendMessage()` 파싱 교체

- [ ] 스트리밍 중 상세 조문 추출 코드를 parser 호출로 교체
- [ ] 완료 시점 상세 조문 추출 코드를 parser 호출로 교체
- [ ] `currentLawDetails` 갱신 방식은 유지
- [ ] 자동 음성 출력, 세션 제목 갱신, 로딩 애니메이션 동작은 유지

완료 기준:

- `sendMessage()` 내부의 직접 `JSONArray` 파싱 중복이 사라진다.
- 채팅 응답 중 상세 조문 버튼/팝업 데이터가 이전과 동일하게 유지된다.

### Task 3. `ChatBubble()` 표시 파싱 교체

- [ ] `actualLawDetails` 계산에 `LegalResponseParser.extractLawDetails()` 사용
- [ ] `mainBodyDisplay`, `legalBasisText`, `lawItems` 계산에 `extractDisplaySections()` 사용
- [ ] `message.lawDetails`가 있으면 우선 사용하는 기존 동작 유지
- [ ] fallback bullet 추출 동작을 필요한 범위에서 유지

완료 기준:

- 본문, 법적 근거, 상세 조문 표시가 기존과 동일하다.
- 파싱 규칙이 `ChatBubble()`에 흩어져 있지 않다.

### Task 4. `ChatStreamManager.kt` URL 구성 정리

- [ ] `buildChatStreamUrl(userText, sessionId, lat, lon)` 추가
- [ ] `URLEncoder.encode`는 URL helper 안에서만 수행
- [ ] 사용하지 않는 `json`, `requestBody` 변수 제거
- [ ] 기존 query parameter 이름 유지: `text`, `uid`, `session_id`, `client_type`, `lat`, `lon`

완료 기준:

- `fetchChatStream()`은 요청 생성과 스트림 처리 흐름이 더 읽기 쉬워진다.
- 서버 API 호출 방식은 바뀌지 않는다.

### Task 5. 빌드 및 수동 검증

- [ ] Android Studio에서 `D:/BaroLaw/frontend` 프로젝트를 연다.
- [ ] `:app` 모듈을 빌드한다.
- [ ] 앱 실행 후 채팅 전송을 확인한다.
- [ ] 스트리밍 응답이 실시간 표시되는지 확인한다.
- [ ] 법적 근거 섹션이 표시되는지 확인한다.
- [ ] 상세 조문 팝업이 열리는지 확인한다.
- [ ] 세션 목록과 히스토리 로드가 유지되는지 확인한다.
- [ ] 자동 음성 출력 옵션이 유지되는지 확인한다.

## 테스트 계획

가능하면 `LegalResponseParser`에 JVM 단위 테스트를 추가한다.

테스트 후보:

- `LEGAL_DETAILS` JSON 배열에서 `LawDetail` 목록 추출
- JSON이 아직 닫히지 않은 스트리밍 중간 상태에서 빈 목록 반환
- `LEGAL_BASIS` 앞의 본문 추출
- `ASSISTANT_ANSWER` 태그가 있을 때 본문 우선 추출
- 태그가 없는 일반 답변은 원문을 본문으로 유지
- 법적 근거 bullet만 `legalBasisItems`로 추출

테스트 파일 후보:

`frontend/app/src/test/java/com/example/barolaw/LegalResponseParserTest.kt`

## 위험 및 대응

### 위험 1. 스트리밍 중간 JSON 파싱

응답이 아직 완성되지 않은 상태에서는 `LEGAL_DETAILS` JSON 배열이 닫히지 않을 수 있다.

대응:

- parser는 예외를 삼키고 빈 리스트를 반환한다.
- 완료 시점에 다시 전체 응답으로 파싱한다.

### 위험 2. 본문과 근거 분리 방식 변화

기존 `ChatBubble()`의 분리 규칙을 잘못 옮기면 표시 순서가 바뀔 수 있다.

대응:

- 기존 분리 우선순위를 유지한다.
- `ASSISTANT_ANSWER`가 있으면 그 뒤를 본문으로 본다.
- 없으면 `LEGAL_BASIS`, `LEGAL_DETAILS` 앞을 본문으로 본다.

### 위험 3. 백엔드 태그 계약 유지 및 전환

Android 1차 리팩터링에서는 백엔드 응답 형식을 바꾸지 않으므로 문자열 태그 의존성은 남는다. 후속 응답 포맷 안정화 작업에서만 `backend/app.py`의 전송 포맷을 제한적으로 다룬다.

대응:

- 태그 의존성을 Android parser 한 파일에 모은다.
- RAG 시스템 파일은 수정하지 않는다.
- 백엔드 포맷 안정화는 `backend/app.py`의 SSE 조립부에 한정한다.
- 전환 시 기존 `message` 기반 `LEGAL_*` 문자열을 즉시 제거하지 않고, 구조화 이벤트를 병행하는 호환 모드를 우선 검토한다.

### 위험 4. `LEGAL_DETAILS` JSON 필드 형식 고정

1차 parser는 현재 백엔드가 실제 전송하는 `title` / `content` 필드 형식을 기준으로 `LawDetail`을 추출한다.

다만 프롬프트 예시나 별도 백엔드 구조화 프로젝트에서는 `statute` / `article` / `content` 형태의 상세 조문 payload가 사용될 가능성이 있다. 이 경우 현재 parser는 제목을 만들 수 없어 해당 항목을 버릴 수 있다.

대응:

- 1차 리팩터링에서는 현재 백엔드 실제 응답 형식인 `title` / `content`만 지원한다.
- Android 1차 리팩터링에서는 현재 백엔드 실제 응답 형식인 `title` / `content`만 지원한다.
- 후속 `backend/app.py` 응답 포맷 안정화 작업에서 `legal_details` payload 스키마를 확정한다.
- 이때도 RAG 결과 생성 방식은 변경하지 않는다.

## 후속 단계

### 2차. 상태 관리 분리

목표:

- 세션 목록, 현재 세션, 메시지 추가, 로딩 애니메이션, 응답 누적을 `MainActivity.kt`에서 분리한다.

후보:

- `ChatSessionController`
- `ChatUiState`
- `ChatViewModel`

### 3차. Compose UI 파일 분리

목표:

- `ChatScreen.kt`
- `ChatBubble.kt`
- `SettingsScreen.kt`
- `LawDetailSheet.kt`

UI 코드를 파일 단위로 분리하되, 상태 구조 변경은 최소화한다.

### 4차. 백엔드 응답 포맷 안정화

상태:

후속 작업. 현재 RAG 시스템 최적화 상태를 보존하기 위해 RAG 검색/랭킹/프롬프트 계층은 변경하지 않고, `backend/app.py`의 SSE 응답 조립부만 제한적으로 다룬다.

목표:

현재 문자열 태그 기반 응답을 구조화 이벤트와 병행해 안정화한다. 기존 Android 호환성을 위해 초기에는 `LEGAL_*` 문자열 태그를 제거하지 않는다.

검토 후보:

예상 이벤트:

```json
{"type": "token", "message": "..."}
{"type": "legal_basis", "items": ["..."]}
{"type": "legal_details", "items": [{"title": "...", "content": "..."}]}
{"type": "metadata", "category": "...", "rag_s": 0.0, "total_s": 0.0}
{"type": "done"}
```

전환 후보:

- 백엔드는 한동안 기존 `message` 필드와 새 `type` 필드를 함께 보낸다.
- Android는 새 `type` 필드가 있으면 우선 사용하고, 없으면 기존 parser를 fallback으로 사용한다.
- 안정화 후 `LEGAL_*` 문자열 파서는 호환 모드로 축소한다.
- `legal_details` payload의 필드 스키마를 확정한다. 현재 Android parser는 `title` / `content`를 기준으로 동작하므로, `statute` / `article` / `content` 형태를 사용할 경우 Android 변환 규칙을 함께 정의한다.

금지:

- `search_relevant_context(...)` 호출 파라미터 변경 금지
- `build_rag_context(...)` 결과 생성 방식 변경 금지
- `MAIN_ENGINE_SYSTEM_PROMPT` 변경 금지
- `preprocessor.analyze(...)` 호출 및 결과 처리 변경 금지
- rerank/boost/sniper/keyword/category 처리 변경 금지

## 결정 사항

- 실제 앱 기준은 `D:/BaroLaw/frontend/app`이다.
- `D:/BaroLaw/android/app`은 이번 리팩터링 범위에서 제외한다.
- 1차 범위는 parser 분리와 `ChatStreamManager.kt` 정리까지다.
- RAG 시스템 변경은 금지한다.
- `backend/app.py`의 SSE 응답 조립/전송 포맷은 후속 안정화 작업에서만 제한적으로 허용한다.

## 다음 액션

1. 이 계획을 검토한다.
2. 1차 리팩터링 실행 여부를 확정한다.
3. 실행 시 `LegalResponseParser.kt`부터 만든다.
4. 각 단계마다 빌드 또는 수동 검증으로 동작 보존을 확인한다.

