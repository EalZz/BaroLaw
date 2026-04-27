package com.example.barolaw.ui

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Gavel
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import com.example.barolaw.LegalResponseParser
import com.example.barolaw.model.ChatMessage
import com.example.barolaw.model.LawDetail
import dev.jeziellago.compose.markdowntext.MarkdownText

@Composable
fun MessageBubble(
    message: ChatMessage,
    onPlayVoice: (String) -> Unit,
    onLawClick: (List<LawDetail>) -> Unit
) {
    val isUser = message.isUser
    val isThinking = !isUser && (message.content.startsWith("Thinking") || message.content == "\uc751\ub2f5\uc744 \uc885\ub8cc\ud588\uc2b5\ub2c8\ub2e4.")
    val bubbleColor = if (isUser) Color(0xFF2F2F2F) else Color.Transparent
    val shape = if (isUser) RoundedCornerShape(20.dp, 20.dp, 4.dp, 20.dp) else RoundedCornerShape(0.dp)
    val clipboardManager = LocalClipboardManager.current
    val context = LocalContext.current

    val actualLawDetails = remember(message.content, message.lawDetails) {
        when {
            message.lawDetails.isNotEmpty() -> message.lawDetails
            isUser -> emptyList()
            else -> LegalResponseParser.extractLawDetails(message.content)
        }
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
        verticalAlignment = Alignment.Top
    ) {
        if (!isUser && isThinking) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .background(Color(0xFF2A2A2A), CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Gavel,
                    contentDescription = null,
                    tint = Color.White,
                    modifier = Modifier.size(24.dp)
                )
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
                        Text(
                            text = message.content,
                            color = if (isThinking) Color.Gray else Color.White,
                            style = MaterialTheme.typography.bodyLarge
                        )
                    } else {
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
                                        text = "\u2696\ufe0f \ubc95\uc801 \uadfc\uac70 \ubc0f \ucc38\uace0 \ubb38\ud5cc",
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
                            Toast.makeText(context, "\ud14d\uc2a4\ud2b8\uac00 \ubcf5\uc0ac\ub418\uc5c8\uc2b5\ub2c8\ub2e4.", Toast.LENGTH_SHORT).show()
                        },
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.ContentCopy,
                            contentDescription = null,
                            tint = Color.Gray,
                            modifier = Modifier.size(16.dp)
                        )
                    }
                    IconButton(
                        onClick = { onPlayVoice(message.content) },
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.VolumeUp,
                            contentDescription = null,
                            tint = Color.Gray,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                    IconButton(
                        onClick = {
                            if (actualLawDetails.isNotEmpty()) {
                                onLawClick(actualLawDetails)
                            } else {
                                Toast.makeText(context, "\uc0c1\uc138 \uc870\ubb38 \ub370\uc774\ud130\ub97c \ubb3c\ub7ec\uc624\ub294 \uc911\uc785\ub2c8\ub2e4...", Toast.LENGTH_SHORT).show()
                            }
                        },
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Gavel,
                            contentDescription = null,
                            tint = Color.Gray,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}
