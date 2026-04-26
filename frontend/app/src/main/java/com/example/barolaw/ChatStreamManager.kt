package com.example.barolaw

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.job
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import org.json.JSONArray
import java.net.URLEncoder
import java.util.concurrent.TimeUnit
import android.content.Context
import android.provider.Settings
import kotlinx.coroutines.withContext

class ChatStreamManager(private val context: Context) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS) // 연결 대기 시간을 1분으로 증설
        .readTimeout(300, TimeUnit.SECONDS)    // 읽기(스트리밍) 시간을 5분으로 증설 (긴 답변 대비)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    private val BASE_URL = "https://welcome-chipmunk-organic.ngrok-free.app"

    // 함수의 반환 타입을 Flow로 명시하고, 내부에서 suspend 기능을 사용합니다.
    fun fetchChatStream(userText: String, sessionId: String, lat: Double? = null, lon: Double? = null): Flow<StreamResponse> = flow {
        val finalUrl = buildChatStreamUrl(userText, sessionId, lat, lon)

        val request = Request.Builder()
            .url(finalUrl)
            .addNgrokHeader()
            .build()

        val call = client.newCall(request)
        
        // Task 5: 코루틴 취소 시 네트워크 호출도 함께 취소되도록 리스너 등록
        val job = currentCoroutineContext().job
        val completionHandler = job.invokeOnCompletion { call.cancel() }

        try {
            val response = call.execute()

            if (!response.isSuccessful) {
                throw Exception("서버 응답 에러: ${response.code}")
            }

            val reader = response.body?.source()?.inputStream()?.bufferedReader()

            // 중요: use를 사용하여 스트림을 안전하게 닫습니다.
            reader?.use { br ->
                while (currentCoroutineContext().isActive) {
                    val line = br.readLine() ?: break
                    if (line.startsWith("data: ")) {
                        val data = line.substring(6)
                        try {
                            val jsonObject = JSONObject(data)
                            val token = jsonObject.optString("message", "")
                            val isDone = jsonObject.optBoolean("done", false)
                            val audioUrl = jsonObject.optString("audio_url").ifBlank { null }

                            // token이 있거나, 혹은 token이 없더라도 isDone이 true라면 emit해야 합니다.
                            if (token.isNotEmpty() || isDone) {
                                emit(StreamResponse(token, isDone, audioUrl))
                            }
                            if (isDone) break
                        } catch (e: Exception) {
                            Log.e("ChatStream", "JSON 파싱 에러: ${e.message}")
                        }
                    }
                }
            }
        } finally {
            completionHandler.dispose()
            call.cancel() // 정상 종료든 취소든 네트워크 연결 확실히 해제
        }
    }.flowOn(Dispatchers.IO) // 이 부분이 핵심: 네트워크 작업은 전용 스레드에서 수행

    suspend fun fetchSessions(uid: String): List<ChatSession> {
        return withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url("$BASE_URL/sessions/$uid")
                .addNgrokHeader()
                .build()
            
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@withContext emptyList()
                val jsonArray = JSONArray(response.body?.string() ?: "[]")
                val list = mutableListOf<ChatSession>()
                for (i in 0 until jsonArray.length()) {
                    val obj = jsonArray.getJSONObject(i)
                    list.add(ChatSession(id = obj.getString("id"), title = obj.getString("title")))
                }
                list
            }
        }
    }

    suspend fun fetchHistory(sessionId: String): List<ChatMessage> {
        return withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url("$BASE_URL/sessions/$sessionId/history")
                .addNgrokHeader()
                .build()
            
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@withContext emptyList()
                val jsonArray = JSONArray(response.body?.string() ?: "[]")
                val list = mutableListOf<ChatMessage>()
                for (i in 0 until jsonArray.length()) {
                    val obj = jsonArray.getJSONObject(i)
                    list.add(ChatMessage(content = obj.getString("content"), isUser = obj.getBoolean("isUser")))
                }
                list
            }
        }
    }

    suspend fun deleteSession(sessionId: String): Boolean {
        return withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url("$BASE_URL/sessions/$sessionId")
                .delete()
                .addNgrokHeader()
                .build()
            
            client.newCall(request).execute().use { response ->
                response.isSuccessful
            }
        }
    }

    private fun buildChatStreamUrl(userText: String, sessionId: String, lat: Double?, lon: Double?): String {
        val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        val encodedText = URLEncoder.encode(userText, "UTF-8")
        
        var url = "$BASE_URL/chat-stream?text=$encodedText&uid=$androidId&session_id=$sessionId&client_type=app"
        if (lat != null && lon != null) {
            url += "&lat=$lat&lon=$lon"
        }
        return url
    }

    private fun Request.Builder.addNgrokHeader() = this.addHeader("ngrok-skip-browser-warning", "true")
}

data class StreamResponse(
    val token: String,
    val isDone: Boolean,
    val audioUrl: String? = null
)
