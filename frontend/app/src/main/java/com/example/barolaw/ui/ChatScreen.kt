package com.example.barolaw.ui

import androidx.compose.animation.*
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Gavel
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.barolaw.model.ChatSession
import com.example.barolaw.model.LawDetail

@Composable
fun ChatScreen(
    currentSession: ChatSession,
    isListening: Boolean,
    voiceLevel: Float,
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
    val micScale by animateFloatAsState(
        targetValue = if (isListening) 1f + (voiceLevel.coerceIn(0f, 1f) * 0.18f) else 1f,
        label = "micPulseScale"
    )

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
                modifier = Modifier
                    .fillMaxWidth()
                    .imePadding()
                    .navigationBarsPadding()
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
                            .scale(micScale)
                            .background(if (isListening) Color.Red else Color.Transparent, CircleShape)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Mic,
                            contentDescription = "Voice",
                            tint = if (isListening) Color.White else Color.Gray
                        )
                    }

                    BasicTextField(
                        value = textState,
                        onValueChange = { textState = it },
                        modifier = Modifier
                            .weight(1f)
                            .padding(horizontal = 8.dp),
                        textStyle = androidx.compose.ui.text.TextStyle(color = Color.White, fontSize = 16.sp),
                        cursorBrush = androidx.compose.ui.graphics.SolidColor(Color.White),
                        decorationBox = { innerTextField ->
                            if (textState.text.isEmpty() && isListening) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    Text("\ub9d0\uc500\ud574 \uc8fc\uc138\uc694...", color = Color(0xFFFFCDD2), fontSize = 16.sp)
                                    VoiceLevelBars(voiceLevel = voiceLevel)
                                }
                            } else if (textState.text.isEmpty()) {
                                Text("\uba54\uc2dc\uc9c0\ub97c \uc785\ub825\ud558\uc138\uc694...", color = Color.Gray, fontSize = 16.sp)
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
                                if (isGenerating || !hasText) Color.DarkGray else Color.White,
                                CircleShape
                            )
                    ) {
                        Icon(
                            imageVector = if (isGenerating) Icons.Default.Stop else Icons.AutoMirrored.Filled.Send,
                            contentDescription = null,
                            tint = if (isGenerating) Color.LightGray else if (hasText) Color.Black else Color.Gray,
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
                    Icon(
                        Icons.Default.Gavel,
                        contentDescription = null,
                        modifier = Modifier.size(64.dp),
                        tint = Color.White
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "\ubb34\uc5c7\uc744 \ub3c4\uc640\ub4dc\ub9b4\uae4c\uc694?",
                        style = MaterialTheme.typography.headlineMedium,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "\uc0c8\ub85c\uc6b4 \uc8fc\uc81c\uc758 \uc0c1\ub2f4\uc740 '\uc0c8 \ucc44\ud305'\uc5d0\uc11c \uc2dc\uc791\ud558\uc2dc\ub294 \uac83\uc774 \uac00\uc7a5 \uc815\ud655\ud569\ub2c8\ub2e4.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Color(0xFF64B5F6),
                        textAlign = TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 32.dp)
                    )
                }
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(
                        top = 100.dp,
                        bottom = innerPadding.calculateBottomPadding() + 8.dp,
                        start = 16.dp,
                        end = 16.dp
                    ),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    items(messages, key = { it.id }) { message ->
                        MessageBubble(message, onPlayVoice, onLawClick)
                    }
                }
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(100.dp)
                    .background(
                        Brush.verticalGradient(
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
                        Icon(Icons.Default.Menu, contentDescription = null, tint = Color.White)
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
private fun VoiceLevelBars(voiceLevel: Float) {
    val level = voiceLevel.coerceIn(0f, 1f)
    val barHeights = listOf(0.35f, 0.65f, 1f, 0.55f)
    Row(
        modifier = Modifier.height(18.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(3.dp)
    ) {
        barHeights.forEach { weight ->
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .height((6 + (level * weight * 12)).dp)
                    .clip(CircleShape)
                    .background(Color(0xFFFFCDD2))
            )
        }
    }
}
