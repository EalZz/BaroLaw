package com.example.voice_chatbot_ct

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
    private var loadingJob: Job? = null
    private var isListening by mutableStateOf(false)
    private var isAutoVoiceEnabled by mutableStateOf(true)
    private var activeScreen by mutableStateOf(ActiveScreen.Chat)

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = android.graphics.Color.TRANSPARENT
        window.navigationBarColor = android.graphics.Color.TRANSPARENT
        
        if (sessions.isEmpty()) {
            createNewSession()
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
                val currentSession = sessions.find { it.id == currentSessionId } ?: sessions[0]

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
                                    items(sessions.reversed()) { session ->
                                        NavigationDrawerItem(
                                            label = { 
                                                Text(
                                                    if(session.title.isEmpty()) "새 대화" else session.title, 
                                                    color = Color.White,
                                                    maxLines = 1
                                                ) 
                                            },
                                            selected = session.id == currentSessionId,
                                            onClick = {
                                                currentSessionId = session.id
                                                scope.launch { drawerState.close() }
                                            },
                                            icon = { Icon(Icons.Default.ChatBubbleOutline, contentDescription = null, tint = Color.Gray) },
                                            colors = NavigationDrawerItemDefaults.colors(
                                                selectedContainerColor = Color(0xFF2C2C34),
                                                unselectedContainerColor = Color.Transparent
                                            )
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
                            onMenuClick = { scope.launch { drawerState.open() } },
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
        val newSession = ChatSession(title = "")
        sessions.add(newSession)
        currentSessionId = newSession.id
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
        val session = sessions.find { it.id == currentSessionId } ?: return
        
        if (session.messages.isEmpty()) {
            val title = if (text.length > 20) text.take(17) + "..." else text
            val idx = sessions.indexOf(session)
            if (idx != -1) sessions[idx] = session.copy(title = title)
        }

        addMessage(text, isUser = true)
        addMessage("Thinking", isUser = false)
        startLoadingAnimation()

        var fullResponse = ""

        lifecycleScope.launch {
            try {
                streamManager.fetchChatStream(text, null, null).collect { response ->
                    if (loadingJob != null) stopLoadingAnimation()

                    val currentSession = sessions.find { it.id == currentSessionId } ?: return@collect
                    val lastIndex = currentSession.messages.size - 1
                    if (lastIndex < 0) return@collect

                    if (response.token.isNotEmpty()) {
                        val currentMessage = currentSession.messages[lastIndex]
                        val newContent = if (currentMessage.content.contains("Thinking")) {
                            response.token
                        } else {
                            currentMessage.content + response.token
                        }
                        currentSession.messages[lastIndex] = currentMessage.copy(content = newContent)
                        fullResponse += response.token
                    }

                    if (response.isDone) {
                        if (fullResponse.isNotBlank() && isAutoVoiceEnabled) {
                            speak(fullResponse)
                        }
                    }
                }
            } catch (e: Exception) {
                stopLoadingAnimation()
                val currentSession = sessions.find { it.id == currentSessionId } ?: return@launch
                val lastIndex = currentSession.messages.size - 1
                if (lastIndex >= 0) {
                    currentSession.messages[lastIndex] = currentSession.messages[lastIndex].copy(content = "에러: ${e.message}")
                }
            }
        }
    }

    private fun addMessage(text: String, isUser: Boolean) {
        val session = sessions.find { it.id == currentSessionId } ?: return
        session.messages.add(ChatMessage(content = text, isUser = isUser))
    }

    private fun startLoadingAnimation() {
        loadingJob = lifecycleScope.launch {
            var dotCount = 1
            while (isActive) {
                val dots = ".".repeat(dotCount)
                val currentSession = sessions.find { it.id == currentSessionId } ?: break
                val lastIndex = currentSession.messages.size - 1
                if (lastIndex >= 0 && !currentSession.messages[lastIndex].isUser && currentSession.messages[lastIndex].content.contains("Thinking")) {
                    currentSession.messages[lastIndex] = currentSession.messages[lastIndex].copy(content = "Thinking$dots")
                }
                dotCount = if (dotCount >= 3) 1 else dotCount + 1
                delay(500)
            }
        }
    }

    private fun stopLoadingAnimation() {
        loadingJob?.cancel()
        loadingJob = null
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
        Box(modifier = Modifier.fillMaxSize()) {
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
                Text(text = message.content, color = if (isThinking) Color.Gray else Color.White, style = MaterialTheme.typography.bodyLarge)
            }
            if (!isUser && !isThinking) {
                IconButton(
                    onClick = { onPlayVoice(message.content) },
                    modifier = Modifier.size(32.dp).padding(top = 4.dp)
                ) {
                    Icon(Icons.Default.PlayArrow, contentDescription = "Play", tint = Color.Gray, modifier = Modifier.size(16.dp))
                }
            }
        }
    }
}
