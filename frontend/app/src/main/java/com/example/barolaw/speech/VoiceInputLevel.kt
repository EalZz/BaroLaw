package com.example.barolaw.speech

object VoiceInputLevel {
    fun normalizeRms(rmsdB: Float): Float {
        return (rmsdB / 10f).coerceIn(0f, 1f)
    }
}
