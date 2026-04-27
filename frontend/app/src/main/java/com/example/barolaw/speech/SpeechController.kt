package com.example.barolaw.speech

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.example.barolaw.LegalResponseParser
import java.util.Locale

class SpeechController(private val context: Context) : TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private var speechRecognizer: SpeechRecognizer? = null
    
    var isListening by mutableStateOf(false)
        private set

    var voiceLevel by mutableStateOf(0f)
        private set
        
    private var lastSpokenText: String? = null

    init {
        tts = TextToSpeech(context, this)
        setupSpeechRecognizer()
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            val result = tts?.setLanguage(Locale.KOREAN)
            if (result != TextToSpeech.LANG_MISSING_DATA && result != TextToSpeech.LANG_NOT_SUPPORTED) {
                // Task 3: 자연스러운 한국어 낭독을 위한 속도 및 피치 미세 조정
                tts?.setSpeechRate(0.98f) // 자연스러운 표준 속도
                tts?.setPitch(1.0f)       // 기본 높낮이 유지

                // 가용 한국어 Voice 중 품질이 높거나 환경에 최적화된 Voice 우선 선택
                try {
                    val voices = tts?.voices
                    if (!voices.isNullOrEmpty()) {
                        val koreanVoices = voices.filter { 
                            it.locale?.language == "ko" || it.locale == Locale.KOREAN || it.locale == Locale.KOREA 
                        }
                        
                        val bestVoice = koreanVoices.filter { !it.isNetworkConnectionRequired }
                            .maxByOrNull { it.quality } 
                            ?: koreanVoices.firstOrNull()

                        bestVoice?.let { tts?.voice = it }
                    }
                } catch (e: Exception) {
                    // Voice 변경 실패 시 기본 한국어 Voice로 자동 Fallback 됨
                }
            }
        }
    }

    private fun setupSpeechRecognizer() {
        if (SpeechRecognizer.isRecognitionAvailable(context)) {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
            speechRecognizer?.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    isListening = true
                    voiceLevel = 0f
                }
                override fun onResults(results: Bundle?) {
                    isListening = false
                    voiceLevel = 0f
                    val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    if (!matches.isNullOrEmpty()) {
                        currentOnResult?.invoke(matches[0])
                    }
                }
                override fun onError(error: Int) {
                    isListening = false
                    voiceLevel = 0f
                }
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {
                    voiceLevel = VoiceInputLevel.normalizeRms(rmsdB)
                }
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() {
                    voiceLevel = 0f
                }
                override fun onPartialResults(partialResults: Bundle?) {}
                override fun onEvent(eventType: Int, params: Bundle?) {}
            })
        }
    }

    private var currentOnResult: ((String) -> Unit)? = null

    fun startListening(onResult: (String) -> Unit) {
        currentOnResult = onResult
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.KOREAN)
        }
        speechRecognizer?.startListening(intent)
    }

    fun stopListening() {
        speechRecognizer?.stopListening()
        isListening = false
        voiceLevel = 0f
    }

    fun toggleVoiceRecognition(onResult: (String) -> Unit) {
        if (isListening) {
            stopListening()
        } else {
            startListening(onResult)
        }
    }

    fun speak(text: String) {
        val cleanBody = try {
            LegalResponseParser.extractDisplaySections(text).mainBody.ifBlank { text }
        } catch (e: Exception) { text }
        
        val cleanText = cleanBody.replace(Regex("[^\\p{L}\\p{N}\\s]"), "")
        lastSpokenText = text
        tts?.speak(cleanText, TextToSpeech.QUEUE_FLUSH, null, null)
    }

    fun stopSpeech() {
        tts?.stop()
        lastSpokenText = null
    }

    fun toggleSpeech(text: String) {
        if (tts?.isSpeaking == true && text == lastSpokenText) {
            stopSpeech()
        } else {
            speak(text)
        }
    }

    fun release() {
        tts?.stop()
        tts?.shutdown()
        speechRecognizer?.destroy()
    }
}
