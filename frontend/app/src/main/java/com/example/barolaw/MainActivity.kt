package com.example.barolaw

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import androidx.lifecycle.lifecycleScope
import com.example.barolaw.model.*
import com.example.barolaw.speech.SpeechController
import com.example.barolaw.ui.ChatScreen
import com.example.barolaw.ui.SettingsScreen
import kotlinx.coroutines.*
import java.util.UUID

// --- Enums ---
enum class ActiveScreen {
    Chat, Settings
}

class MainActivity : ComponentActivity() {

    private lateinit var speechController: SpeechController
    private val streamManager = ChatStreamManager(this)
    private var selectedLawDetails by mutableStateOf<List<LawDetail>?>(null)
    private val sessions = mutableStateListOf<ChatSession>()
    private var currentSessionId by mutableStateOf("")
    
    // UI states
    private val loadingJobs = mutableMapOf<String, Job>()
    private var isAutoVoiceEnabled by mutableStateOf(false)
    private var activeScreen by mutableStateOf(ActiveScreen.Chat)
    private var showDeleteDialog by mutableStateOf(false)
    private var sessionToDelete by mutableStateOf<ChatSession?>(null)

    // Generation states
    private var activeGenerationSessionId by mutableStateOf<String?>(null)
    private var activeGenerationMessageId by mutableStateOf<String?>(null)
    private var generationJob: Job? = null
    private val locallyStoppedSessionIds = mutableSetOf<String>()

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = android.graphics.Color.TRANSPARENT
        window.navigationBarColor = android.graphics.Color.TRANSPARENT
        
        val androidId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID)
        lifecycleScope.launch {
            try {
                val savedSessions = streamManager.fetchSessions(androidId)
                if (savedSessions.isNotEmpty()) {
                    sessions.clear()
                    sessions.addAll(savedSessions)
                }
            } catch (e: Exception) {}
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
            != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), 100)
        }

        speechController = SpeechController(this)

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

                Box(modifier = Modifier.fillMaxSize()) {

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
                                            if (currentSessionId == session.id) currentSessionId = ""
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
                                    items(sessions) { session -> 
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
                            isListening = speechController.isListening,
                            voiceLevel = speechController.voiceLevel,
                            isGenerating = activeGenerationSessionId == currentSession.id,
                            onSendMessage = { text -> sendMessage(text) },
                            onStopGeneration = { stopGeneration() },
                            onVoiceClick = { speechController.toggleVoiceRecognition(onResult = { sendMessage(it) }) },
                            onMenuClick = { 
                                refreshSessionTitles()
                                scope.launch { drawerState.open() } 
                            },
                            onPlayVoice = { text -> speechController.toggleSpeech(text) },
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
                                .pointerInput(Unit) { detectTapGestures { selectedLawDetails = null } },
                            contentAlignment = Alignment.Center
                        ) {
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth(0.9f)
                                    .fillMaxHeight(0.7f)
                                    .padding(16.dp)
                                    .pointerInput(Unit) { detectTapGestures { } },
                                shape = RoundedCornerShape(28.dp),
                                colors = CardDefaults.cardColors(containerColor = Color(0xFF1A1A1A)),
                                elevation = CardDefaults.cardElevation(defaultElevation = 12.dp)
                            ) {
                                Column(modifier = Modifier.padding(24.dp)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(text = "\u2696\ufe0f 상세 법적 근거", style = MaterialTheme.typography.titleLarge, color = Color.White)
                                        IconButton(onClick = { selectedLawDetails = null }) {
                                            Icon(Icons.Default.Close, contentDescription = "Close", tint = Color.Gray)
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(16.dp))
                                    LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                                        items(details) { detail ->
                                            Column {
                                                Text(text = detail.title, style = MaterialTheme.typography.titleMedium, color = Color.White)
                                                Spacer(modifier = Modifier.height(8.dp))
                                                SelectionContainer {
                                                    Text(text = detail.content, style = MaterialTheme.typography.bodyLarge.copy(lineHeight = 24.sp), color = Color.LightGray)
                                                }
                                                if (details.indexOf(detail) < details.size - 1) {
                                                    Spacer(modifier = Modifier.height(16.dp))
                                                    HorizontalDivider(color = Color.DarkGray)
                                                }
                                            }
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(16.dp))
                                    Text(text = "\ud31d\uc5c5 \ubc16\uc744 \ub204\ub974\uba74 \ub2eb\ud799\ub2c8\ub2e4.", style = MaterialTheme.typography.labelMedium, color = Color.DarkGray, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center)
                                }
                            }
                        }
                    }
                }
                }
            }
        }
    }

    private fun createNewSession() {
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
                        sessions.add(updated)
                    }
                }
            } catch (e: Exception) {}
        }
    }

    private fun loadHistory(sessionId: String) {
        if (sessionId == activeGenerationSessionId || sessionId in locallyStoppedSessionIds) return
        lifecycleScope.launch {
            try {
                val history = streamManager.fetchHistory(sessionId)
                val session = sessions.find { it.id == sessionId }
                if (session != null) {
                    session.messages.clear()
                    session.messages.addAll(history)
                }
            } catch (e: Exception) {}
        }
    }

    private fun sendMessage(text: String) {
        if (currentSessionId.isEmpty()) {
            val newSession = ChatSession(id = UUID.randomUUID().toString(), title = text.take(15) + "...")
            sessions.add(0, newSession)
            currentSessionId = newSession.id
        }
        
        val activeSessionId = currentSessionId
        val session = sessions.find { it.id == activeSessionId } ?: return
        locallyStoppedSessionIds.remove(activeSessionId)
        
        if (session.messages.isEmpty()) {
            val title = if (text.length > 20) text.take(17) + "..." else text
            val idx = sessions.indexOf(session)
            if (idx != -1) sessions[idx] = session.copy(title = title)
        }

        if (generationJob?.isActive == true) return

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
                        stopLoadingAnimation(aiMsgId)
                        val targetSession = sessions.find { it.id == activeSessionId } ?: return@collect
                        val msgIndex = targetSession.messages.indexOfFirst { it.id == aiMsgId }
                        if (msgIndex >= 0) {
                            val msg = targetSession.messages[msgIndex]
                            val newContent = if (msg.content.contains("Thinking")) token else msg.content + token
                            fullResponse += token
                            val extractedDetails = LegalResponseParser.extractLawDetails(fullResponse)
                            if (extractedDetails.isNotEmpty()) {
                                currentLawDetails.clear()
                                currentLawDetails.addAll(extractedDetails)
                            }
                            targetSession.messages[msgIndex] = msg.copy(content = newContent, lawDetails = currentLawDetails.toList())
                        }
                    }
                    if (response.isDone) {
                        stopLoadingAnimation(aiMsgId)
                        if (fullResponse.isNotBlank() && isAutoVoiceEnabled) {
                            speechController.speak(fullResponse)
                        }
                        val extracted = LegalResponseParser.extractLawDetails(fullResponse)
                        val finalDetails = if (extracted.isNotEmpty()) extracted else currentLawDetails.toList()
                        val targetSession = sessions.find { it.id == activeSessionId }
                        val msgIndex = targetSession?.messages?.indexOfFirst { it.id == aiMsgId } ?: -1
                        if (msgIndex >= 0) {
                            targetSession!!.messages[msgIndex] = targetSession.messages[msgIndex].copy(lawDetails = finalDetails)
                        }
                        lifecycleScope.launch { delay(2000); refreshSessionTitles() }
                    }
                }
            } catch (e: CancellationException) {
                stopLoadingAnimation(aiMsgId)
            } catch (e: Exception) {
                stopLoadingAnimation(aiMsgId)
                val targetSession = sessions.find { it.id == activeSessionId }
                val msgIndex = targetSession?.messages?.indexOfFirst { it.id == aiMsgId } ?: -1
                if (msgIndex >= 0) {
                    val currentMsg = targetSession!!.messages[msgIndex]
                    targetSession.messages[msgIndex] = currentMsg.copy(content = "\uc624\ub958 \ubc1c\uc0dd: ${e.localizedMessage}")
                }
            } finally {
                if (activeGenerationSessionId == activeSessionId) {
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

    private fun stopGeneration() {
        val sid = activeGenerationSessionId
        val msgId = activeGenerationMessageId
        val jobToCancel = generationJob
        msgId?.let { stopLoadingAnimation(it) }
        if (sid != null) {
            locallyStoppedSessionIds.add(sid)
            val session = sessions.find { it.id == sid }
            val msgIndex = session?.messages?.indexOfFirst { it.id == msgId } ?: -1
            if (msgIndex >= 0) {
                val msg = session!!.messages[msgIndex]
                if (msg.content.contains("Thinking")) session.messages[msgIndex] = msg.copy(content = "\uc751\ub2f5\uc744 \uc885\ub8cc\ud588\uc2b5\ub2c8\ub2e4.")
            }
        }
        lifecycleScope.launch {
            if (sid != null) streamManager.cancelChat(sid)
            jobToCancel?.cancel()
            if (generationJob == jobToCancel) generationJob = null
        }
        speechController.stopSpeech()
        speechController.stopListening()
    }

    override fun onDestroy() {
        speechController.release()
        super.onDestroy()
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (activeScreen == ActiveScreen.Settings) activeScreen = ActiveScreen.Chat
        else moveTaskToBack(true)
    }
}

