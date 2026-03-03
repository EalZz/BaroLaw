package com.example.voice_chatbot_ct

import android.net.Uri
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.net.URLEncoder
import java.util.concurrent.TimeUnit
import android.content.Context
import android.provider.Settings

class ChatStreamManager(private val context: Context) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS) // 연결 대기 시간을 1분으로 증설
        .readTimeout(300, TimeUnit.SECONDS)    // 읽기(스트리밍) 시간을 5분으로 증설 (긴 답변 대비)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    private val BASE_URL = "https://welcome-chipmunk-organic.ngrok-free.app"

    // 함수의 반환 타입을 Flow로 명시하고, 내부에서 suspend 기능을 사용합니다.
    fun fetchChatStream(userText: String, lat: Double? = null, lon: Double? = null): Flow<StreamResponse> = flow {
        val json = JSONObject().put("text", userText).toString()
        val requestBody = json.toRequestBody("application/json".toMediaType())
        val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        val encodedText = URLEncoder.encode(userText, "UTF-8")

        var finalUrl = "$BASE_URL/chat-stream?text=$encodedText&uid=$androidId&client_type=app"

        if (lat != null && lon != null) {
            finalUrl += "&lat=$lat&lon=$lon"
        }

        val request = Request.Builder()
            .url(finalUrl)
            .addHeader("ngrok-skip-browser-warning", "true") // ngrok 우회 헤더
            .build()

        // 콜백 방식이 아닌 동기 실행 후 response를 받아 처리합니다.
        // 이 블록 전체가 flow 내부(코루틴 환경)이므로 emit 호출이 가능해집니다.
        val response = client.newCall(request).execute()

        if (!response.isSuccessful) {
            throw Exception("서비 응답 에러: ${response.code}")
        }

        val reader = response.body?.source()?.inputStream()?.bufferedReader()

        // 중요: use를 사용하여 스트림을 안전하게 닫습니다.
        reader?.use { br ->
            var line: String? = br.readLine()
            while (line != null) {
                if (line.startsWith("data: ")) {
                    val data = line.substring(6)
                    try {
                        val jsonObject = JSONObject(data)
                        val token = jsonObject.optString("message", "")
                        val isDone = jsonObject.optBoolean("done", false)
                        val audioUrl = jsonObject.optString("audio_url", null)

                        // token이 있거나, 혹은 token이 없더라도 isDone이 true라면 emit해야 합니다.
                        if (token.isNotEmpty() || isDone) {
                            emit(StreamResponse(token, isDone, audioUrl))
                        }
                    } catch (e: Exception) {
                        Log.e("ChatStream", "JSON 파싱 에러: ${e.message}")
                    }
                }
                line = br.readLine()
            }
        }
    }.flowOn(Dispatchers.IO) // 이 부분이 핵심: 네트워크 작업은 전용 스레드에서 수행
}

data class StreamResponse(
    val token: String,
    val isDone: Boolean,
    val audioUrl: String? = null
)