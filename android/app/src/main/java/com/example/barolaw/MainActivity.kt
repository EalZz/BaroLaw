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
data class ChatMessage(
    val content: String, 
    val isUser: Boolean, 
    val id: String = UUID.randomUUID().toString()
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

    // Sessions state
    private val sessions = mutableStateListOf<ChatSession>()
    private var currentSessionId by mutableStateOf("")
    
    // UI states
    private val loadingJobs = mutableMapOf<String, Job>()
    private var isListening by mutableStateOf(false)
    private var isAutoVoiceEnabled by mutableStateOf(false)
    private var activeScreen by mutableStateOf(ActiveScreen.Chat)
    private var showDeleteDialog by mutableStateOf(false)
    private var sessionToDelete by mutableStateOf<ChatSession?>(null)

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
                // sessions가 비어있거나 currentSessionId가 없는 경우 가상의 빈 세션 반환 (메인 가이드용)
                val currentSession = sessions.find { it.id == currentSessionId } ?: ChatSession(id = "", title = "메인 가이드")

                if (showDeleteDialog && sessionToDelete != null) {
                    AlertDialog(
                        onDismissRequest = { 
                            showDeleteDialog = false
                            sessionToDelete = null
                        },
                        title = { Text("대화방 삭제", color = Color.White) },
                        text = { Text("이 대화방을 삭제하시겠습니까?\n삭제된 내용은 복구할 수 없습니다.", color = Color.White) },
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
                            onSendMessage = { text -> sendMessage(text) },
                            onVoiceClick = { toggleVoiceRecognition() },
                            onMenuClick = { 
                                refreshSessionTitles()
                                scope.launch { drawerState.open() } 
                            },
                            onPlayVoice = { text -> speak(text) }
                        )
                    }
                } else {
                    SettingsScreen(
                        isAutoVoiceEnabled = isAutoVoiceEnabled,
                        onToggleVoice = { isAutoVoiceEnabled = it },
                        onBack = { activeScreen = ActiveScreen.Chat }
                    )
                }
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

        addMessage(activeSessionId, text, isUser = true)
        val aiMsgId = addMessage(activeSessionId, "Thinking", isUser = false)
        startLoadingAnimation(activeSessionId, aiMsgId)

        var fullResponse = ""

        lifecycleScope.launch {
            try {
                streamManager.fetchChatStream(text, activeSessionId, null, null).collect { response ->
                    val token = response.token
                    if (token.isNotEmpty()) {
                        stopLoadingAnimation(aiMsgId) // 실제 텍스트가 올 때만 멈춤

                        val targetSession = sessions.find { it.id == activeSessionId } ?: return@collect
                        val msgIndex = targetSession.messages.indexOfFirst { it.id == aiMsgId }
                        if (msgIndex >= 0) {
                            val msg = targetSession.messages[msgIndex]
                            val newContent = if (msg.content.contains("Thinking")) token else msg.content + token
                            targetSession.messages[msgIndex] = msg.copy(content = newContent)
                            fullResponse += token
                        }
                    }

                    if (response.isDone) {
                        stopLoadingAnimation(aiMsgId)
                        if (fullResponse.isNotBlank() && isAutoVoiceEnabled) {
                            speak(fullResponse)
                        }
                        
                        // [자동 갱신] 스트리밍 답변이 끝났다면, 서버의 요약도 끝났을 확률이 높으므로 즉시 제목 동기화
                        lifecycleScope.launch {
                            delay(2000) // 혹시 모를 짧은 스트리밍 대비 서버 DB Commit 대기
                            refreshSessionTitles()
                        }
                    }
                }
            } catch (e: Exception) {
                stopLoadingAnimation(aiMsgId)
                val targetSession = sessions.find { it.id == activeSessionId } ?: return@launch
                val msgIndex = targetSession.messages.indexOfFirst { it.id == aiMsgId }
                if (msgIndex >= 0) {
                    val currentMsg = targetSession.messages[msgIndex]
                    targetSession.messages[msgIndex] = currentMsg.copy(content = "오류 발생: ${e.localizedMessage}")
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
        val cleanText = text.replace(Regex("[^\\p{L}\\p{N}\\s]"), "")
        tts.speak(cleanText, TextToSpeech.QUEUE_FLUSH, null, null)
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
    onSendMessage: (String) -> Unit,
    onVoiceClick: () -> Unit,
    onMenuClick: () -> Unit,
    onPlayVoice: (String) -> Unit
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
                            val trimmed = textState.text.trim()
                            if (trimmed.isNotEmpty()) {
                                onSendMessage(trimmed)
                                textState = TextFieldValue("")
                            }
                        },
                        modifier = Modifier
                            .size(40.dp)
                            .background(if (hasText) Color.White else Color.DarkGray, CircleShape)
                    ) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.Send, 
                            contentDescription = "Send", 
                            tint = if (hasText) Color.Black else Color.Gray,
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
                        ChatBubble(message, onPlayVoice)
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
fun ChatBubble(message: ChatMessage, onPlayVoice: (String) -> Unit) {
    val isUser = message.isUser
    val isThinking = !isUser && message.content.startsWith("Thinking")
    val bubbleColor = if (isUser) Color(0xFF2F2F2F) else Color.Transparent
    val shape = if (isUser) RoundedCornerShape(20.dp, 20.dp, 4.dp, 20.dp) else RoundedCornerShape(0.dp)
    val clipboardManager = LocalClipboardManager.current
    val context = LocalContext.current

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
                        val parts = message.content.split("\n\n---[LEGAL_BASIS]---\n").toMutableList()
                        // 혹시 과거의 \n\n---\n 포맷이 남아있을 경우를 대비
                        if (parts.size == 1) {
                            parts.clear()
                            parts.addAll(message.content.split("\n\n---\n"))
                        }
                        
                        if (parts.size > 1 && !isThinking) {
                            Column {
                                MarkdownText(
                                    markdown = parts[0],
                                    color = Color.White,
                                    style = MaterialTheme.typography.bodyLarge,
                                    isTextSelectable = true
                                )
                                Spacer(modifier = Modifier.height(16.dp))
                                HorizontalDivider(color = Color.DarkGray)
                                Spacer(modifier = Modifier.height(8.dp))
                                MarkdownText(
                                    markdown = parts.drop(1).joinToString("\n\n---[LEGAL_BASIS]---\n").replace("\n\n---\n", ""),
                                    color = Color.Gray,
                                    style = MaterialTheme.typography.bodyMedium,
                                    isTextSelectable = true
                                )
                            }
                        } else {
                            MarkdownText(
                                markdown = message.content,
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
                }
            }
        }
    }
}
