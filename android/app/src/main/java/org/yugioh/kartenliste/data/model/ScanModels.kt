package org.yugioh.kartenliste.data.model

data class ScanSignals(
    val rawText: String,
    val setCodes: List<String>,
    val passcodes: List<String>,
    val possibleNames: List<String>,
    val atk: Int? = null,
    val def: Int? = null,
    val level: Int? = null,
    val detectedScripts: Set<String> = emptySet(),
)

data class ScanCandidate(
    val card: Card,
    val matchedPrint: CardPrint?,
    val score: Int,
    val reason: String,
)

data class ScanResult(
    val sourceLabel: String,
    val signals: ScanSignals,
    val candidates: List<ScanCandidate>,
    val error: String? = null,
) {
    val best: ScanCandidate? get() = candidates.maxByOrNull { it.score }
}

data class ScanBatchState(
    val total: Int = 0,
    val completed: Int = 0,
    val results: List<ScanResult> = emptyList(),
    val running: Boolean = false,
)
