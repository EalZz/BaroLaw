package com.example.barolaw.model

import androidx.compose.runtime.mutableStateListOf
import java.util.UUID

data class LawDetail(val title: String, val content: String)

data class ChatMessage(
    val content: String, 
    val isUser: Boolean, 
    val id: String = UUID.randomUUID().toString(),
    val lawDetails: List<LawDetail> = emptyList()
)

data class ChatSession(
    val id: String = UUID.randomUUID().toString(),
    val title: String,
    val messages: MutableList<ChatMessage> = mutableStateListOf()
)
