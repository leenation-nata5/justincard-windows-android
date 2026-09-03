package org.yugioh.kartenliste.ui

import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import org.yugioh.kartenliste.data.JustInCardDatabase

enum class DisplayContext(val key: String, val label: String) {
    SEARCH("search", "Suche"),
    COLLECTION("collection", "Sammlung"),
    DECKS("decks", "Decks"),
    SCANNER("scanner", "Scanner"),
}

enum class DisplayField(val key: String, val label: String) {
    SET_CODE("set_code", "Set-Code"),
    SET_NAME("set_name", "Set"),
    RARITY("rarity", "Seltenheit"),
    LANGUAGE("language", "Sprache"),
    ARTWORK("artwork", "Artwork / Alt Art"),
    TYPE("type", "Kartentyp"),
    RACE("race", "Typ / Rasse"),
    ATTRIBUTE("attribute", "Attribut"),
    STATS("stats", "ATK / DEF / Level"),
    MARKET("market", "Marktwert"),
}

class DisplayPrefs(private val db: JustInCardDatabase) {
    private val gson = Gson()
    private val profileType = object : TypeToken<Map<String, Map<String, Boolean>>>() {}.type
    private val setting = "display_profiles_android_v1"

    fun load(): Map<String, Map<String, Boolean>> {
        val raw = db.getSetting(setting)
        val parsed: Map<String, Map<String, Boolean>> = runCatching {
            gson.fromJson<Map<String, Map<String, Boolean>>>(raw, profileType)
        }.getOrNull() ?: emptyMap()

        val result = linkedMapOf<String, Map<String, Boolean>>()
        for (context in DisplayContext.entries) {
            val fields = linkedMapOf<String, Boolean>()
            for (field in DisplayField.entries) {
                fields[field.key] = parsed[context.key]?.get(field.key) ?: true
            }
            result[context.key] = fields
        }
        return result
    }

    fun enabled(context: DisplayContext, field: DisplayField): Boolean =
        load()[context.key]?.get(field.key) ?: true

    fun set(context: DisplayContext, field: DisplayField, enabled: Boolean) {
        val current = load()
        val updated = linkedMapOf<String, MutableMap<String, Boolean>>()
        for ((key, values) in current) {
            updated[key] = values.toMutableMap()
        }
        val contextMap = updated.getOrPut(context.key) { linkedMapOf() }
        contextMap[field.key] = enabled
        db.setSetting(setting, gson.toJson(updated))
    }
}
