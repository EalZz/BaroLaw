package com.example.barolaw

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.*
import java.util.Locale
import androidx.core.view.WindowCompat
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.sp
import androidx.compose.ui.platform.LocalDensity
import java.util.UUID
import android.provider.Settings
import dev.jeziellago.compose.markdowntext.MarkdownText
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import android.widget.Toast
import androidx.compose.ui.platform.LocalContext

// --- Enums ---
enum class ActiveScreen {
    Chat, Settings
}

// --- Data Models ---
data class LawDetail(val title: String, val content: String)

data class ChatMessage(
    val content: String, 
    val isUser: Boolean, 
    val id: String = UUID.randomUUID().toString(),
    val lawDetails: List<LawDetail> = emptyList() // 상세 조문 데이터 추가
)

data class ChatSession(
    val id: String = UUID.randomUUID().toString(),
    val title: String,
    val messages: MutableList<ChatMessage> = mutableStateListOf()
)

class MainActivity : ComponentActivity(), TextToSpeech.OnInitListener {

    private lateinit var tts: TextToSpeech
    private lateinit var speechRecognizer: SpeechRecognizer
    private val streamManager = ChatStreamManager(this)
    private var selectedLawDetails by mutableStateOf<List<LawDetail>?>(null) // 팝업용 상태 (여러 조문 동시 표시)
    private val sessions = mutableStateListOf<ChatSession>()
    private var currentSessionId by mutableStateOf("")
    
    // UI states
    private val loadingJobs = mutableMapOf<String, Job>()
    private var isListening by mutableStateOf(false)
    private var isAutoVoiceEnabled by mutableStateOf(false)
    private var activeScreen by mutableStateOf(ActiveScreen.Chat)
    private var showDeleteDialog by mutableStateOf(false)
    private var sessionToDelete by mutableStateOf<ChatSession?>(null)

    // Generation states
    private var activeGenerationSessionId by mutableStateOf<String?>(null)
    private var activeGenerationMessageId by mutableStateOf<String?>(null)
    private var generationJob: Job? = null
    private var lastSpokenText: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = android.graphics.Color.TRANSPARENT
        window.navigationBarColor = android.graphics.Color.TRANSPARENT
        
        // UI가 렌더링될 때 빈 세션 에러가 나지 않도록 일단 빈 세션 1개 생성 (제외: 이제 메인 가이드가 기본)
        // if (sessions.isEmpty()) {
        //     createNewSession()
        // }

        val androidId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID)
        lifecycleScope.launch {
            try {
                val savedSessions = streamManager.fetchSessions(androidId)
                if (savedSessions.isNotEmpty()) {
                    sessions.clear()
                    sessions.addAll(savedSessions)
                    // 앱 실행 시에는 가장 최근 세션을 바로 로드하지 않고 메인 화면(빈 세션 아이디)을 유지하거나 선택 가능
                    // currentSessionId = savedSessions.first().id
                    // loadHistory(currentSessionId)
                }
            } catch (e: Exception) {
                // 에러 무시
            }
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), 100)
        }

        tts = TextToSpeech(this, this)
        setupSpeechRecognizer()

        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    background = Color(0xFF121212),
                    surface = Color(0xFF1E1E1E),
                    primary = Color(0xFF3F51B5),
                    secondary = Color(0xFFE91E63)
                )
            ) {
                val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
                val scope = rememberCoroutineScope()
                val currentSession = sessions.find { it.id == currentSessionId } ?: ChatSession(id = "", title = "메인 가이드")

                // 전체 화면을 Box로 감싸 오버레이 레이어를 구성합니다.
                Box(modifier = Modifier.fillMaxSize()) {

                if (showDeleteDialog && sessionToDelete != null) {
                    AlertDialog(
                        onDismissRequest = { 
                            showDeleteDialog = false
                            sessionToDelete = null
                        },
                        title = { Text("대화방 삭제", color = Color.White) },
                        text = { Text("이 대화방을 삭제하시겠습니까?\n삭제된 내용은 복구할 수 복구할 수 없습니다.", color = Color.White) },
                        confirmButton = {
                            TextButton(onClick = {
                                sessionToDelete?.let { session ->
                                    scope.launch {
                                        val success = streamManager.deleteSession(session.id)
                                        if (success) {
                                            sessions.remove(session)
                                            if (currentSessionId == session.id) {
                                                currentSessionId = ""
                                            }
                                        }
                                    }
                                }
                                showDeleteDialog = false
                                sessionToDelete = null
                            }) {
                                Text("삭제", color = Color.Red)
                            }
                        },
                        dismissButton = {
                            TextButton(onClick = { 
                                showDeleteDialog = false
                                sessionToDelete = null
                            }) {
                                Text("취소", color = Color.White)
                            }
                        },
                        containerColor = Color(0xFF1E1E1E)
                    )
                }

                if (activeScreen == ActiveScreen.Chat) {
                    ModalNavigationDrawer(
                        drawerState = drawerState,
                        drawerContent = {
                            ModalDrawerSheet(
                                modifier = Modifier.width(300.dp).background(Color(0xFF1E1E24))
                            ) {
                                Spacer(modifier = Modifier.height(48.dp))
                                
                                NavigationDrawerItem(
                                    label = { Text("새 채팅", color = Color.White) },
                                    selected = false,
                                    onClick = {
                                        createNewSession()
                                        scope.launch { drawerState.close() }
                                    },
                                    icon = { Icon(Icons.Default.Add, contentDescription = null, tint = Color.White) },
                                    colors = NavigationDrawerItemDefaults.colors(unselectedContainerColor = Color.Transparent)
                                )
                                
                                HorizontalDivider(modifier = Modifier.padding(vertical = 8.dp), color = Color.DarkGray)
                                
                                Text(
                                    "채팅 목록",
                                    modifier = Modifier.padding(start = 16.dp, top = 8.dp, bottom = 8.dp),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = Color.Gray
                                )
                                LazyColumn(modifier = Modifier.weight(1f)) {
                                    items(sessions) { session -> // 정렬은 백엔드에서 이미 updated_at 기준 내림차순으로 줌
                                        NavigationDrawerItem(
                                            label = { 
                                                Row(
                                                    modifier = Modifier.fillMaxWidth(),
                                                    verticalAlignment = Alignment.CenterVertically,
                                                    horizontalArrangement = Arrangement.SpaceBetween
                                                ) {
                                                    Text(
                                                        if(session.title.isEmpty()) "새 대화" else session.title, 
                                                        color = Color.White,
                                                        maxLines = 1,
                                                        modifier = Modifier.weight(1f)
                                                    )
                                                    
                                                    IconButton(
                                                        onClick = { 
                                                            sessionToDelete = session
                                                            showDeleteDialog = true
                                                        },
                                                        modifier = Modifier.size(24.dp)
                                                    ) {
                                                        Icon(
                                                            imageVector = Icons.Default.Delete,
                                                            contentDescription = "Delete",
                                                            tint = Color.Gray,
                                                            modifier = Modifier.size(16.dp)
                                                        )
                                                    }
                                                }
                                            },
                                            selected = session.id == currentSessionId,
                                            onClick = {
                                                currentSessionId = session.id
                                                loadHistory(session.id)
                                                scope.launch { drawerState.close() }
                                            },
                                            icon = { Icon(Icons.Default.ChatBubbleOutline, contentDescription = null, tint = Color.Gray) },
                                            colors = NavigationDrawerItemDefaults.colors(
                                                selectedContainerColor = Color(0xFF2C2C34),
                                                unselectedContainerColor = Color.Transparent
                                            ),
                                            modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding)
                                        )
                                    }
                                }

                                HorizontalDivider(color = Color.DarkGray)
                                
                                NavigationDrawerItem(
                                    label = { Text("환경설정", color = Color.White) },
                                    selected = false,
                                    onClick = {
                                        activeScreen = ActiveScreen.Settings
                                        scope.launch { drawerState.close() }
                                    },
                                    icon = { Icon(Icons.Default.Settings, contentDescription = null, tint = Color.White) },
                                    colors = NavigationDrawerItemDefaults.colors(unselectedContainerColor = Color.Transparent)
                                )
                                Spacer(modifier = Modifier.height(16.dp))
                            }
                        }
                    ) {
                        ChatScreen(
                            currentSession = currentSession,
                            isListening = isListening,
                            isGenerating = activeGenerationSessionId == currentSession.id,
                            onSendMessage = { text -> sendMessage(text) },
                            onStopGeneration = { stopGeneration() },
                            onVoiceClick = { toggleVoiceRecognition() },
                            onMenuClick = { 
                                refreshSessionTitles()
                                scope.launch { drawerState.open() } 
                            },
                            onPlayVoice = { text -> toggleSpeech(text) },
                            onLawClick = { details -> selectedLawDetails = details }
                        )
                    }
                } else {
                    SettingsScreen(
                        isAutoVoiceEnabled = isAutoVoiceEnabled,
                        onToggleVoice = { isAutoVoiceEnabled = it },
                        onBack = { activeScreen = ActiveScreen.Chat }
                    )
                }

                // --- 상세 조문 팝업 오버레이 (Z-Index 최상단) ---
                AnimatedVisibility(
                    visible = selectedLawDetails != null,
                    enter = fadeIn() + expandVertically(),
                    exit = fadeOut() + shrinkVertically()
                ) {
                    selectedLawDetails?.let { details ->
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .background(Color.Black.copy(alpha = 0.7f))
                                .pointerInput(Unit) {
                                    detectTapGestures { selectedLawDetails = null }
                                },
                            contentAlignment = Alignment.Center
                        ) {
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth(0.9f)
                                    .fillMaxHeight(0.7f)
                                    .padding(16.dp)
                                    .pointerInput(Unit) { detectTapGestures { /* 팝업 내부 터치는 무시 */ } },
                                shape = RoundedCornerShape(28.dp),
                                colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A)), // 남색 톤 제거, 완전한 무채색 다크그레이
                                elevation = CardDefaults.cardElevation(defaultElevation = 12.dp)
                            ) {
                                Column(modifier = Modifier.padding(24.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            text = "⚖️ 상세 법적 근거",
                                            style = MaterialTheme.typography.titleLarge,
                                            color = Color.White
                                        )
                                        IconButton(onClick = { selectedLawDetails = null }) {
                                            Icon(Icons.Default.Close, contentDescription = "Close", tint = Color.Gray)
                                        }
                                    }
                                    
                                    Spacer(modifier = Modifier.height(16.dp))
                                    
                                    LazyColumn(
                                        modifier = Modifier.weight(1f),
                                        verticalArrangement = Arrangement.spacedBy(16.dp)
                                    ) {
                                        items(details) { detail ->
                                            Column {
                                                Text(
                                                    text = detail.title,
                                                    style = MaterialTheme.typography.titleMedium,
                                                    color = Color.White // 파란색에서 흰색(무채색)으로 변경
                                                )
                                                Spacer(modifier = Modifier.height(8.dp))
                                                SelectionContainer {
                                                    Text(
                                                        text = detail.content,
                                                        style = MaterialTheme.typography.bodyLarge.copy(lineHeight = 24.sp),
                                                        color = Color.LightGray // 본문은 연한 회색으로 가독성 확보
                                                    )
                                                }
                                                if (details.indexOf(detail) < details.size - 1) {
                                                    Spacer(modifier = Modifier.height(16.dp))
                                                    HorizontalDivider(color = Color.DarkGray)
                                                }
                                            }
                                        }
                                    }
                                    
                                    Spacer(modifier = Modifier.height(16.dp))
                                    Text(
                                        text = "팝업 밖을 누르면 닫힙니다.",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = Color.DarkGray,
                                        modifier = Modifier.fillMaxWidth(),
                                        textAlign = TextAlign.Center
                                    )
                                }
                            }
                        }
                    }
                }
            } // Box end
            }
        }
    }

    private fun createNewSession() {
        // 이제 단순히 currentSessionId를 비워서 메인 화면으로 돌아가게 함
        currentSessionId = ""
    }

    private fun refreshSessionTitles() {
        val androidId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID)
        lifecycleScope.launch {
            try {
                val updatedSessions = streamManager.fetchSessions(androidId)
                updatedSessions.forEach { updated ->
                    val index = sessions.indexOfFirst { it.id == updated.id }
                    if (index != -1) {
                        val existing = sessions[index]
                        if (existing.title != updated.title && updated.title.isNotEmpty()) {
                            sessions[index] = existing.copy(title = updated.title)
                        }
                    } else {
                        // 만약 로컬에 없는 완전히 새로운 세션이 서버에 생겼을 경우 (이론상 방어 코드)
                        sessions.add(updated)
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    private fun loadHistory(sessionId: String) {
        lifecycleScope.launch {
            try {
                val history = streamManager.fetchHistory(sessionId)
                val session = sessions.find { it.id == sessionId }
                if (session != null) {
                    session.messages.clear()
                    session.messages.addAll(history)
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    private fun setupSpeechRecognizer() {
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this)
        speechRecognizer.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) { isListening = true }
            override fun onResults(results: Bundle?) {
                isListening = false
                val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if (!matches.isNullOrEmpty()) sendMessage(matches[0])
            }
            override fun onError(error: Int) { isListening = false }
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
    }

    private fun toggleVoiceRecognition() {
        if (isListening) {
            speechRecognizer.stopListening()
        } else {
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.KOREAN)
            }
            speechRecognizer.startListening(intent)
        }
    }

    private fun sendMessage(text: String) {
        // [지연 생성] 현재 선택된 세션이 없거나 세션이 비어있는 경우 새로 생성
        if (currentSessionId.isEmpty()) {
            val newSession = ChatSession(id = UUID.randomUUID().toString(), title = text.take(15) + "...")
            sessions.add(0, newSession) // 최상단에 추가
            currentSessionId = newSession.id
        }
        
        val activeSessionId = currentSessionId // !!핵심!! 현재 세션 ID 캡처
        val session = sessions.find { it.id == activeSessionId } ?: return
        
        if (session.messages.isEmpty()) {
            val title = if (text.length > 20) text.take(17) + "..." else text
            val idx = sessions.indexOf(session)
            if (idx != -1) sessions[idx] = session.copy(title = title)
        }

        if (generationJob?.isActive == true) return // 중복 전송 방지

        addMessage(activeSessionId, text, isUser = true)
        val aiMsgId = addMessage(activeSessionId, "Thinking", isUser = false)
        startLoadingAnimation(activeSessionId, aiMsgId)

        activeGenerationSessionId = activeSessionId
        activeGenerationMessageId = aiMsgId

        var fullResponse = ""
        val currentLawDetails = mutableListOf<LawDetail>()

        generationJob = lifecycleScope.launch {
            try {
                streamManager.fetchChatStream(text, activeSessionId, null, null).collect { response ->
                    val token = response.token
                    if (token.isNotEmpty()) {
                        stopLoadingAnimation(aiMsgId) // 법적 근거가 먼저 오더라도 로딩 애니메이션 종료

                        val targetSession = sessions.find { it.id == activeSessionId } ?: return@collect
                        val msgIndex = targetSession.messages.indexOfFirst { it.id == aiMsgId }
                        if (msgIndex >= 0) {
                            val msg = targetSession.messages[msgIndex]

                            val newContent = if (msg.content.contains("Thinking")) token else msg.content + token
                            fullResponse += token

                            // [보충] 파서 호출로 중복 로직 제거
                            val extractedDetails = LegalResponseParser.extractLawDetails(fullResponse)
                            if (extractedDetails.isNotEmpty()) {
                                currentLawDetails.clear()
                                currentLawDetails.addAll(extractedDetails)
                            }

                            targetSession.messages[msgIndex] = msg.copy(
                                content = newContent,
                                lawDetails = currentLawDetails.toList()
                            )
                        }
                    }

                    if (response.isDone) {
                        stopLoadingAnimation(aiMsgId)
                        if (fullResponse.isNotBlank() && isAutoVoiceEnabled) {
                            val cleanBody = LegalResponseParser.extractDisplaySections(fullResponse).mainBody
                            speak(cleanBody)
                        }
                        
                        // [최종 확정] 파서 호출로 스트리밍 종료 시점 데이터 누락 방지
                        val extracted = LegalResponseParser.extractLawDetails(fullResponse)
                        val finalDetails = if (extracted.isNotEmpty()) extracted else currentLawDetails.toList()
                        
                        val targetSession = sessions.find { it.id == activeSessionId }
                        val msgIndex = targetSession?.messages?.indexOfFirst { it.id == aiMsgId } ?: -1
                        if (msgIndex >= 0) {
                            targetSession!!.messages[msgIndex] = targetSession.messages[msgIndex].copy(
                                lawDetails = finalDetails
                            )
                        }
                        
                        // [자동 갱신] 스트리밍 답변이 끝났다면, 서버의 요약도 끝났을 확률이 높으므로 즉시 제목 동기화
                        lifecycleScope.launch {
                            delay(2000) // 혹시 모를 짧은 스트리밍 대비 서버 대기
                            refreshSessionTitles()
                        }
                    }
                }
            } catch (e: CancellationException) {
                // 사용자가 정지 버튼을 누른 경우이므로 무시 (오류 메시지로 덮어쓰지 않음)
                stopLoadingAnimation(aiMsgId)
            } catch (e: Exception) {
                stopLoadingAnimation(aiMsgId)
                val targetSession = sessions.find { it.id == activeSessionId }
                val msgIndex = targetSession?.messages?.indexOfFirst { it.id == aiMsgId } ?: -1
                if (msgIndex >= 0) {
                    val currentMsg = targetSession!!.messages[msgIndex]
                    targetSession.messages[msgIndex] = currentMsg.copy(content = "오류 발생: ${e.localizedMessage}")
                }
            } finally {
                // 어떤 경우에도 상태 초기화
                if (activeGenerationSessionId == activeSessionId && activeGenerationMessageId == aiMsgId) {
                    activeGenerationSessionId = null
                    activeGenerationMessageId = null
                    generationJob = null
                }
            }
        }
    }

    private fun addMessage(sessionId: String, text: String, isUser: Boolean): String {
        val session = sessions.find { it.id == sessionId } ?: return ""
        val newMsg = ChatMessage(content = text, isUser = isUser)
        session.messages.add(newMsg)
        return newMsg.id
    }

    private fun startLoadingAnimation(targetSessionId: String, msgId: String) {
        val job = lifecycleScope.launch {
            var dotCount = 1
            while (isActive) {
                val dots = ".".repeat(dotCount)
                val targetSession = sessions.find { it.id == targetSessionId } ?: break
                val msgIndex = targetSession.messages.indexOfFirst { it.id == msgId }
                if (msgIndex >= 0 && !targetSession.messages[msgIndex].isUser && targetSession.messages[msgIndex].content.contains("Thinking")) {
                    targetSession.messages[msgIndex] = targetSession.messages[msgIndex].copy(content = "Thinking$dots")
                }
                dotCount = if (dotCount >= 3) 1 else dotCount + 1
                delay(500)
            }
        }
        loadingJobs[msgId] = job
    }

    private fun stopLoadingAnimation(msgId: String) {
        loadingJobs[msgId]?.cancel()
        loadingJobs.remove(msgId)
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) tts.language = Locale.KOREAN
    }

    private fun speak(text: String) {
        val cleanBody = try {
            LegalResponseParser.extractDisplaySections(text).mainBody.ifBlank { text }
        } catch (e: Exception) { text }
        
        val cleanText = cleanBody.replace(Regex("[^\\p{L}\\p{N}\\s]"), "")
        lastSpokenText = text // 원문 기준으로 추적
        tts.speak(cleanText, TextToSpeech.QUEUE_FLUSH, null, null)
    }

    private fun toggleSpeech(text: String) {
        if (tts.isSpeaking && text == lastSpokenText) {
            tts.stop()
            lastSpokenText = null
        } else {
            speak(text)
        }
    }

    private fun stopGeneration() {
        generationJob?.cancel()
        generationJob = null

        activeGenerationMessageId?.let { msgId ->
            stopLoadingAnimation(msgId)
            
            activeGenerationSessionId?.let { sid ->
                val session = sessions.find { it.id == sid }
                val msgIndex = session?.messages?.indexOfFirst { it.id == msgId } ?: -1
                if (msgIndex >= 0) {
                    val msg = session!!.messages[msgIndex]
                    // Thinking 상태면 중단 메시지로 교체
                    if (msg.content.contains("Thinking")) {
                        session.messages[msgIndex] = msg.copy(content = "생성이 중단되었습니다")
                    }
                }
            }
        }

        if (tts.isSpeaking) {
            tts.stop()
            lastSpokenText = null
        }
        
        if (isListening) {
            speechRecognizer.stopListening()
            isListening = false
        }

        activeGenerationSessionId = null
        activeGenerationMessageId = null
    }

    override fun onDestroy() {
        if (::tts.isInitialized) { tts.stop(); tts.shutdown() }
        if (::speechRecognizer.isInitialized) speechRecognizer.destroy()
        super.onDestroy()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (activeScreen == ActiveScreen.Settings) {
            activeScreen = ActiveScreen.Chat
        } else {
            // 앱 종료 대신 백그라운드로 보냄
            moveTaskToBack(true)
        }
    }
}

@Composable
fun ChatScreen(
    currentSession: ChatSession,
    isListening: Boolean,
    isGenerating: Boolean,
    onSendMessage: (String) -> Unit,
    onStopGeneration: () -> Unit,
    onVoiceClick: () -> Unit,
    onMenuClick: () -> Unit,
    onPlayVoice: (String) -> Unit,
    onLawClick: (List<LawDetail>) -> Unit
) {
    val messages = currentSession.messages
    var textState by remember { mutableStateOf(TextFieldValue("")) }
    val listState = rememberLazyListState()
    val focusManager = LocalFocusManager.current

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        containerColor = Color(0xFF121212),
        bottomBar = {
            Surface(
                color = Color(0xFF121212),
                modifier = Modifier.fillMaxWidth().imePadding().navigationBarsPadding()
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 12.dp)
                        .background(Color(0xFF2A2A2A), CircleShape)
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(
                        onClick = onVoiceClick,
                        modifier = Modifier
                            .size(40.dp)
                            .background(if (isListening) Color.Red else Color.Transparent, CircleShape)
                    ) {
                        Icon(imageVector = Icons.Default.Mic, contentDescription = "Voice", tint = if (isListening) Color.White else Color.Gray)
                    }
                    
                    BasicTextField(
                        value = textState,
                        onValueChange = { textState = it },
                        modifier = Modifier.weight(1f).padding(horizontal = 8.dp),
                        textStyle = androidx.compose.ui.text.TextStyle(color = Color.White, fontSize = 16.sp),
                        cursorBrush = androidx.compose.ui.graphics.SolidColor(Color.White),
                        decorationBox = { innerTextField ->
                            if (textState.text.isEmpty()) {
                                Text("메시지를 입력하세요...", color = Color.Gray, fontSize = 16.sp)
                            }
                            innerTextField()
                        }
                    )
                    
                    val hasText = textState.text.trim().isNotEmpty()
                    IconButton(
                        onClick = {
                            if (isGenerating) {
                                onStopGeneration()
                            } else {
                                val trimmed = textState.text.trim()
                                if (trimmed.isNotEmpty()) {
                                    onSendMessage(trimmed)
                                    textState = TextFieldValue("")
                                }
                            }
                        },
                        modifier = Modifier
                            .size(40.dp)
                            .background(
                                if (isGenerating) Color.DarkGray // 회색 배경
                                else if (hasText) Color.White 
                                else Color.DarkGray, 
                                CircleShape
                            )
                    ) {
                        Icon(
                            imageVector = if (isGenerating) Icons.Default.Stop else Icons.AutoMirrored.Filled.Send, 
                            contentDescription = if (isGenerating) "Stop" else "Send", 
                            tint = if (isGenerating) Color.LightGray // 좀 더 밝은 회색
                                   else if (hasText) Color.Black 
                                   else Color.Gray,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .pointerInput(Unit) {
                    detectTapGestures(onTap = { focusManager.clearFocus() })
                }
        ) {
            if (messages.isEmpty()) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Icon(Icons.Default.Gavel, contentDescription = "Logo", modifier = Modifier.size(64.dp), tint = Color.White)
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(text = "무엇을 도와드릴까요?", style = MaterialTheme.typography.headlineMedium, color = Color.White)
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "새로운 주제의 상담은 '새 채팅'에서 시작하시는 것이 가장 정확합니다.",
                        style = MaterialTheme.typography.bodyMedium, color = Color(0xFF64B5F6), // 가시성 높은 파란색 톤
                        textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 32.dp)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "본 챗봇의 내용은 참고용이며, 정확한 판단은 법률 전문가와의 상담을 권장합니다.",
                        style = MaterialTheme.typography.bodySmall, color = Color.Gray,
                        textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 32.dp)
                    )
                }
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(
                        top = 100.dp,
                        bottom = innerPadding.calculateBottomPadding() + 8.dp,
                        start = 16.dp, end = 16.dp
                    ),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    items(messages, key = { it.id }) { message ->
                        ChatBubble(message, onPlayVoice, onLawClick)
                    }
                }
            }

            // Top Bar with Gradient
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(100.dp)
                    .background(
                        brush = Brush.verticalGradient(
                            colors = listOf(Color(0xFF121212), Color.Transparent)
                        )
                    )
                    .statusBarsPadding()
                    .padding(horizontal = 16.dp, vertical = 8.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxSize(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(onClick = onMenuClick) {
                        Icon(imageVector = Icons.Default.Menu, contentDescription = "Menu", tint = Color.White)
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    if (messages.isNotEmpty()) {
                        Text(
                            text = currentSession.title,
                            color = Color.White,
                            style = MaterialTheme.typography.titleMedium,
                            maxLines = 1
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun SettingsScreen(
    isAutoVoiceEnabled: Boolean,
    onToggleVoice: (Boolean) -> Unit,
    onBack: () -> Unit
) {
    Scaffold(
        modifier = Modifier.fillMaxSize(),
        containerColor = Color(0xFF121212),
        topBar = {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(imageVector = Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Color.White)
                }
                Spacer(modifier = Modifier.width(8.dp))
                Text("환경설정", color = Color.White, style = MaterialTheme.typography.titleMedium)
            }
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("음성 출력 사용", color = Color.White, fontSize = 18.sp)
                Switch(
                    checked = isAutoVoiceEnabled,
                    onCheckedChange = { onToggleVoice(it) },
                    colors = SwitchDefaults.colors(
                        checkedThumbColor = Color.White,
                        checkedTrackColor = Color.DarkGray,
                        uncheckedThumbColor = Color.Gray,
                        uncheckedTrackColor = Color.Black
                    )
                )
            }
            HorizontalDivider(color = Color.DarkGray)
        }
    }
}

@Composable
fun ChatBubble(
    message: ChatMessage, 
    onPlayVoice: (String) -> Unit,
    onLawClick: (List<LawDetail>) -> Unit
) {
    val isUser = message.isUser
    val isThinking = !isUser && (message.content.startsWith("Thinking") || message.content == "생성이 중단되었습니다")
    val bubbleColor = if (isUser) Color(0xFF2F2F2F) else Color.Transparent
    val shape = if (isUser) RoundedCornerShape(20.dp, 20.dp, 4.dp, 20.dp) else RoundedCornerShape(0.dp)
    val clipboardManager = LocalClipboardManager.current
    val context = LocalContext.current
    
    // [리팩터링] 중앙 집중화된 파서를 사용하여 데이터 일관성 확보
    val actualLawDetails = remember(message.content, message.lawDetails) {
        when {
            message.lawDetails.isNotEmpty() -> message.lawDetails
            isUser -> emptyList()
            else -> {
                val parsedDetails = LegalResponseParser.extractLawDetails(message.content)
                if (parsedDetails.isNotEmpty()) {
                    parsedDetails
                } else {
                    val fallbackMessage = if (message.content.contains(LegalResponseParser.DETAILS_TAG)) {
                        "상세 조문 데이터를 불러오는 중입니다..."
                    } else {
                        "상세 내용은 백엔드에서 불러오지 못했습니다. (법조문 제목만 표시)"
                    }
                    LegalResponseParser.extractFallbackLawDetails(message.content, fallbackMessage)
                }
            }
        }
    }

    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
        verticalAlignment = Alignment.Top
    ) {
        if (!isUser && isThinking) {
            Box(
                modifier = Modifier.size(36.dp).background(Color(0xFF2A2A2A), CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Icon(Icons.Default.Gavel, contentDescription = "AI", tint = Color.White, modifier = Modifier.size(24.dp))
            }
            Spacer(modifier = Modifier.width(12.dp))
        }

        Column(
            modifier = Modifier.weight(1f, fill = false),
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
        ) {
            Box(
                modifier = Modifier
                    .widthIn(max = if (isUser) 280.dp else 1000.dp)
                    .clip(shape)
                    .background(bubbleColor)
                    .padding(horizontal = if (isUser) 16.dp else 0.dp, vertical = if (isUser) 12.dp else 4.dp)
            ) {
                SelectionContainer {
                    if (isUser) {
                        Text(text = message.content, color = if (isThinking) Color.Gray else Color.White, style = MaterialTheme.typography.bodyLarge)
                    } else {
                        // [파싱 전략 통합] LegalResponseParser를 사용하여 본문과 근거를 분리합니다.
                        val sections = remember(message.content) {
                            LegalResponseParser.extractDisplaySections(message.content)
                        }

                        if (sections.mainBody.isNotEmpty() || sections.legalBasis.isNotEmpty()) {
                                Column(modifier = Modifier.fillMaxWidth()) {
                                    if (sections.mainBody.isNotEmpty()) {
                                        MarkdownText(
                                            markdown = sections.mainBody,
                                            color = if (isThinking) Color.Gray else Color.White,
                                            style = MaterialTheme.typography.bodyLarge,
                                            isTextSelectable = true
                                        )
                                    }
                                    
                                    if (sections.legalBasis.isNotEmpty()) {
                                        if (sections.mainBody.isNotEmpty()) {
                                            Spacer(modifier = Modifier.height(16.dp))
                                            HorizontalDivider(color = Color.DarkGray)
                                            Spacer(modifier = Modifier.height(8.dp))
                                        }
                                        
                                        Text(
                                            text = "⚖️ 법적 근거 및 참고 문헌",
                                            color = Color.Gray,
                                            style = MaterialTheme.typography.titleSmall,
                                            modifier = Modifier.padding(bottom = 4.dp)
                                        )
                                        
                                        sections.legalBasisItems.forEach { item ->
                                            Text(
                                                text = item,
                                                color = Color.Gray,
                                                style = MaterialTheme.typography.bodyMedium,
                                                modifier = Modifier.padding(vertical = 4.dp)
                                            )
                                        }
                                    }
                                }
                        } else {
                            // 아직 아무것도 파싱되지 않았거나 Thinking/중단 상태일 때
                            MarkdownText(
                                markdown = sections.mainBody.ifBlank { message.content.trim() },
                                color = if (isThinking) Color.Gray else Color.White,
                                style = MaterialTheme.typography.bodyLarge,
                                isTextSelectable = true
                            )
                        }
                    }
                }
            }
            if (!isThinking) {
                Row(
                    modifier = Modifier.padding(top = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(
                        onClick = {
                            clipboardManager.setText(AnnotatedString(message.content))
                            Toast.makeText(context, "텍스트가 복사되었습니다.", Toast.LENGTH_SHORT).show()
                        },
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(Icons.Default.ContentCopy, contentDescription = "Copy", tint = Color.Gray, modifier = Modifier.size(16.dp))
                    }
                    IconButton(
                        onClick = { onPlayVoice(message.content) },
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(Icons.Default.VolumeUp, contentDescription = "Play", tint = Color.Gray, modifier = Modifier.size(18.dp))
                    }
                    // [개선] 법률 데이터 로딩 여부와 상관없이 복사/음성 버튼과 함께 항상 노출합니다.
                    IconButton(
                        onClick = { 
                            if (actualLawDetails.isNotEmpty()) {
                                onLawClick(actualLawDetails)
                            } else {
                                Toast.makeText(context, "상세 조문 데이터를 불러오는 중입니다...", Toast.LENGTH_SHORT).show()
                            }
                        },
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(Icons.Default.Gavel, contentDescription = "Law", tint = Color.Gray, modifier = Modifier.size(18.dp))
                    }
                }
            }
        }
    }
}
