package org.yugioh.kartenliste.sync

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import org.yugioh.kartenliste.data.local.AppPreferences
import org.yugioh.kartenliste.data.model.CardCondition
import org.yugioh.kartenliste.data.model.CardKey
import org.yugioh.kartenliste.data.model.CardPrint
import org.yugioh.kartenliste.data.model.CollectionItem
import org.yugioh.kartenliste.data.model.Deck
import org.yugioh.kartenliste.data.model.DeckCard
import org.yugioh.kartenliste.data.model.DeckSection
import org.yugioh.kartenliste.data.repository.CollectionRepository
import org.yugioh.kartenliste.data.repository.DeckRepository
import java.io.File
import java.security.MessageDigest
import java.util.Locale

class AccountSyncEngine(
    context: Context,
    private val preferences: AppPreferences,
    private val collection: CollectionRepository,
    private val decks: DeckRepository,
    private val api: AccountApiClient = AccountApiClient(),
) {
    private val baseFile = File(context.filesDir, "account_sync_base_v1.json")
    private val mutex = Mutex()

    val isLoggedIn: Boolean get() = preferences.accountToken.isNotBlank()

    suspend fun login(identity: String, password: String): AccountLoginResult = withContext(Dispatchers.IO) {
        val result = api.login(identity, password, preferences.deviceName)
        // A base from another account must never participate in a three-way merge.
        runCatching { baseFile.delete() }
        preferences.accountToken = result.token
        preferences.accountLabel = result.label
        preferences.accountMode = "account"
        preferences.accountAutomaticSync = true
        result
    }

    suspend fun logout() = withContext(Dispatchers.IO) {
        val token = preferences.accountToken
        runCatching { api.logout(token) }
        preferences.accountToken = ""
        preferences.accountLabel = ""
        preferences.accountMode = "local"
        runCatching { baseFile.delete() }
    }

    fun useLocalMode() {
        preferences.accountMode = "local"
    }

    suspend fun loadAfterLogin(): AccountSyncReport = mutex.withLock {
        withContext(Dispatchers.IO) {
            val token = preferences.accountToken
            if (token.isBlank()) throw AccountApiException("Bitte zuerst mit deinem Just-InCard-Konto anmelden.", 401, "unauthorized")

            val remote = api.getSnapshot(token)
            val remoteCollection = remote.payload.optJSONArray("collection")?.length() ?: 0
            val remoteDecks = remote.payload.optJSONArray("decks")?.length() ?: 0
            val hasRemoteData = remoteCollection > 0 || remoteDecks > 0

            if (hasRemoteData) {
                // First login is a restore operation: never upload an unrelated
                // local database before the account snapshot has been loaded.
                applyPayload(remote.payload)
                saveBase(remote.payload)
                preferences.accountLastSyncAt = System.currentTimeMillis()
                return@withContext AccountSyncReport(remote.revision, remoteCollection, remoteDecks)
            }

            // A genuinely empty new account may be initialized from the current
            // device so existing local collections are not lost.
            val local = buildLocalPayload()
            val localCollection = local.optJSONArray("collection")?.length() ?: 0
            val localDecks = local.optJSONArray("decks")?.length() ?: 0
            val revision = if (localCollection > 0 || localDecks > 0) {
                api.putSnapshot(token, local, remote.revision, preferences.deviceName)
            } else {
                remote.revision
            }
            saveBase(if (localCollection > 0 || localDecks > 0) local else remote.payload)
            preferences.accountLastSyncAt = System.currentTimeMillis()
            AccountSyncReport(revision, localCollection, localDecks)
        }
    }

    suspend fun sync(): AccountSyncReport = mutex.withLock {
        withContext(Dispatchers.IO) {
            val token = preferences.accountToken
            if (token.isBlank()) throw AccountApiException("Bitte zuerst mit deinem Just-InCard-Konto anmelden.", 401, "unauthorized")

            val base = loadBase()
            val local = inheritUnmodeledFields(buildLocalPayload(), base)
            var remoteResult = api.getSnapshot(token)
            var merged = mergePayloads(base, local, remoteResult.payload)
            val revision = try {
                api.putSnapshot(token, merged, remoteResult.revision, preferences.deviceName)
            } catch (error: AccountApiException) {
                if (error.status != 409) throw error
                remoteResult = api.getSnapshot(token)
                merged = mergePayloads(base, local, remoteResult.payload)
                api.putSnapshot(token, merged, remoteResult.revision, preferences.deviceName)
            }

            applyPayload(merged)
            saveBase(merged)
            preferences.accountLastSyncAt = System.currentTimeMillis()
            AccountSyncReport(
                revision = revision,
                collectionCount = merged.optJSONArray("collection")?.length() ?: 0,
                deckCount = merged.optJSONArray("decks")?.length() ?: 0,
            )
        }
    }

    private suspend fun buildLocalPayload(): JSONObject {
        val collectionRows = collection.allForSync().filter { !it.deleted && it.quantity > 0 }.map { item ->
            val syncId = collectionIdentity(
                item.cardKey.cardId,
                item.cardKey.artworkId,
                item.selectedPrint.setCode,
                item.selectedPrint.rarity,
                item.condition.label,
                item.language,
            )
            JSONObject()
                .put("sync_id", syncId)
                .put("card_id", item.cardKey.cardId)
                .put("artwork_id", item.cardKey.artworkId)
                .put("card_name", item.cardName)
                .put("set_code", item.selectedPrint.setCode)
                .put("set_name", item.selectedPrint.setName)
                .put("rarity", item.selectedPrint.rarity)
                .put("language", item.language)
                .put("condition", item.condition.label)
                .put("quantity", item.quantity)
                .put("notes", item.notes)
                .put("added_at_ms", item.updatedAt)
                .put("updated_at_ms", item.updatedAt)
                .put("device_id", item.deviceId.ifBlank { preferences.deviceId })
        }
        val deckRows = decks.allForSync().filter { !it.deleted }.map { deck ->
            val deckSyncId = deckIdentity(deck.name)
            val cards = deck.cards.filter { !it.deleted && it.quantity > 0 }.map { card ->
                JSONObject()
                    .put("sync_id", deckCardIdentity(deckSyncId, card.cardKey.cardId, card.cardKey.artworkId, card.setCode, card.section.name))
                    .put("card_id", card.cardKey.cardId)
                    .put("artwork_id", card.cardKey.artworkId)
                    .put("language", card.cardKey.language)
                    .put("card_name", card.cardName)
                    .put("set_code", card.setCode)
                    .put("section", card.section.name)
                    .put("quantity", card.quantity)
                    .put("updated_at_ms", card.updatedAt)
                    .put("device_id", card.deviceId.ifBlank { preferences.deviceId })
            }
            JSONObject()
                .put("sync_id", deckSyncId)
                .put("name", deck.name)
                .put("notes", deck.notes)
                .put("updated_at_ms", deck.updatedAt)
                .put("device_id", deck.deviceId.ifBlank { preferences.deviceId })
                .put("cards", JSONArray(cards))
        }
        return JSONObject()
            .put("schema", AccountApiClient.ACCOUNT_SCHEMA)
            .put("collection", JSONArray(collectionRows))
            .put("decks", JSONArray(deckRows))
    }

    private suspend fun applyPayload(payload: JSONObject) {
        val collectionItems = objects(payload.optJSONArray("collection")).mapNotNull(::toCollectionItem)
        val deckItems = objects(payload.optJSONArray("decks")).mapNotNull(::toDeck)
        collection.replaceAll(collectionItems)
        decks.replaceAll(deckItems)
    }

    private fun toCollectionItem(row: JSONObject): CollectionItem? {
        val cardId = row.optLong("card_id", 0L)
        if (cardId <= 0L) return null
        val artworkId = row.optLong("artwork_id", cardId).takeIf { it > 0L } ?: cardId
        val language = row.optString("language", "en").ifBlank { "en" }
        val setCode = row.optString("set_code")
        val print = CardPrint(
            cardId = cardId,
            setName = row.optString("set_name"),
            setCode = setCode,
            rarity = row.optString("rarity"),
            language = language,
        )
        val conditionValue = row.optString("condition")
        val condition = CardCondition.entries.firstOrNull {
            it.name.equals(conditionValue, true) || it.label.equals(conditionValue, true)
        } ?: CardCondition.NEAR_MINT
        return CollectionItem(
            id = row.optString("sync_id").ifBlank { collectionIdentity(cardId, artworkId, setCode, print.rarity, condition.label, language) },
            cardKey = CardKey(cardId, artworkId, language),
            cardName = row.optString("card_name").ifBlank { "Karte $cardId" },
            imageUrl = artworkUrl(artworkId),
            selectedPrint = print,
            condition = condition,
            language = language,
            quantity = row.optInt("quantity", 1).coerceAtLeast(0),
            notes = row.optString("notes"),
            updatedAt = row.optLong("updated_at_ms", System.currentTimeMillis()),
            deviceId = row.optString("device_id").ifBlank { preferences.deviceId },
            deleted = false,
        )
    }

    private fun toDeck(row: JSONObject): Deck? {
        val name = row.optString("name").trim().ifBlank { "Deck" }
        val deckId = row.optString("sync_id").ifBlank { deckIdentity(name) }
        val cards = objects(row.optJSONArray("cards")).mapNotNull { card ->
            val cardId = card.optLong("card_id", 0L)
            if (cardId <= 0L) return@mapNotNull null
            val artworkId = card.optLong("artwork_id", cardId).takeIf { it > 0L } ?: cardId
            val language = card.optString("language", "en").ifBlank { "en" }
            val section = runCatching { DeckSection.valueOf(card.optString("section", "MAIN").uppercase(Locale.ROOT)) }
                .getOrDefault(DeckSection.MAIN)
            DeckCard(
                id = card.optString("sync_id").ifBlank { deckCardIdentity(deckId, cardId, artworkId, card.optString("set_code"), section.name) },
                deckId = deckId,
                cardKey = CardKey(cardId, artworkId, language),
                cardName = card.optString("card_name").ifBlank { "Karte $cardId" },
                imageUrl = artworkUrl(artworkId),
                setCode = card.optString("set_code"),
                section = section,
                quantity = card.optInt("quantity", 1).coerceAtLeast(0),
                updatedAt = card.optLong("updated_at_ms", System.currentTimeMillis()),
                deviceId = card.optString("device_id").ifBlank { preferences.deviceId },
                deleted = false,
            )
        }
        return Deck(
            id = deckId,
            name = name,
            notes = row.optString("notes"),
            cards = cards,
            updatedAt = row.optLong("updated_at_ms", cards.maxOfOrNull { it.updatedAt } ?: System.currentTimeMillis()),
            deviceId = row.optString("device_id").ifBlank { preferences.deviceId },
            deleted = false,
        )
    }

    private fun inheritUnmodeledFields(local: JSONObject, base: JSONObject): JSONObject {
        val baseCollection = objectMap(base.optJSONArray("collection"))
        objects(local.optJSONArray("collection")).forEach { item ->
            val previous = baseCollection[item.optString("sync_id")] ?: return@forEach
            if (previous.has("added_at_ms")) item.put("added_at_ms", previous.optLong("added_at_ms"))
        }

        val baseDecks = objectMap(base.optJSONArray("decks"))
        objects(local.optJSONArray("decks")).forEach { deck ->
            val previous = baseDecks[deck.optString("sync_id")] ?: return@forEach
            if (previous.has("favorite")) deck.put("favorite", previous.optBoolean("favorite"))
        }
        return local
    }

    private fun mergePayloads(basePayload: JSONObject, localPayload: JSONObject, remotePayload: JSONObject): JSONObject {
        val base = normalizePayload(basePayload)
        val local = normalizePayload(localPayload)
        val remote = normalizePayload(remotePayload)
        val mergedCollection = mergeRecordMaps(
            objects(base.optJSONArray("collection")),
            objects(local.optJSONArray("collection")),
            objects(remote.optJSONArray("collection")),
        )

        val baseDecks = objectMap(base.optJSONArray("decks"))
        val localDecks = objectMap(local.optJSONArray("decks"))
        val remoteDecks = objectMap(remote.optJSONArray("decks"))
        val deckKeys = (baseDecks.keys + localDecks.keys + remoteDecks.keys).toSortedSet()
        val mergedDecks = mutableListOf<JSONObject>()
        deckKeys.forEach { key ->
            val b = baseDecks[key]
            val l = localDecks[key]
            val r = remoteDecks[key]
            val meta = mergeRecordMaps(
                listOfNotNull(b?.without("cards")),
                listOfNotNull(l?.without("cards")),
                listOfNotNull(r?.without("cards")),
            ).firstOrNull() ?: return@forEach
            val cards = mergeRecordMaps(
                objects(b?.optJSONArray("cards")),
                objects(l?.optJSONArray("cards")),
                objects(r?.optJSONArray("cards")),
            )
            meta.put("cards", JSONArray(cards))
            val cardMax = cards.maxOfOrNull { it.optLong("updated_at_ms", 0L) } ?: 0L
            meta.put("updated_at_ms", maxOf(meta.optLong("updated_at_ms", 0L), cardMax))
            mergedDecks += meta
        }

        return JSONObject()
            .put("schema", AccountApiClient.ACCOUNT_SCHEMA)
            .put("collection", JSONArray(mergedCollection))
            .put("decks", JSONArray(mergedDecks))
    }

    private fun mergeRecordMaps(
        baseItems: List<JSONObject>,
        localItems: List<JSONObject>,
        remoteItems: List<JSONObject>,
    ): List<JSONObject> {
        val base = baseItems.associateBy { it.optString("sync_id") }.filterKeys { it.isNotBlank() }
        val local = localItems.associateBy { it.optString("sync_id") }.filterKeys { it.isNotBlank() }
        val remote = remoteItems.associateBy { it.optString("sync_id") }.filterKeys { it.isNotBlank() }
        val keys = (base.keys + local.keys + remote.keys).toSortedSet()
        return buildList {
            keys.forEach { key ->
                val b = base[key]
                val l = local[key]
                val r = remote[key]
                val chosen: JSONObject? = if (b == null) {
                    when {
                        l == null -> r
                        r == null -> l
                        same(l, r) -> l
                        else -> winner(l, r)
                    }
                } else {
                    val lChanged = !same(l, b)
                    val rChanged = !same(r, b)
                    when {
                        !lChanged && !rChanged -> b
                        lChanged && !rChanged -> l
                        rChanged && !lChanged -> r
                        l == null && r == null -> null
                        l == null -> r // concurrent deletion/change: keep the changed data
                        r == null -> l
                        else -> winner(l, r)
                    }
                }
                if (chosen != null) add(JSONObject(chosen.toString()))
            }
        }
    }

    private fun same(a: JSONObject?, b: JSONObject?): Boolean {
        if (a == null || b == null) return a == null && b == null
        return canonical(a.without("updated_at_ms", "device_id")) == canonical(b.without("updated_at_ms", "device_id"))
    }

    private fun winner(a: JSONObject, b: JSONObject): JSONObject {
        val ta = a.optLong("updated_at_ms", 0L)
        val tb = b.optLong("updated_at_ms", 0L)
        if (ta != tb) return if (ta > tb) a else b
        return if (a.optString("device_id") >= b.optString("device_id")) a else b
    }

    private fun normalizePayload(payload: JSONObject?): JSONObject {
        val p = payload ?: AccountApiClient.emptyPayload()
        return JSONObject()
            .put("schema", AccountApiClient.ACCOUNT_SCHEMA)
            .put("collection", JSONArray(objects(p.optJSONArray("collection"))))
            .put("decks", JSONArray(objects(p.optJSONArray("decks")).map { deck ->
                JSONObject(deck.toString()).put("cards", JSONArray(objects(deck.optJSONArray("cards"))))
            }))
    }

    private fun loadBase(): JSONObject = runCatching {
        if (!baseFile.isFile) AccountApiClient.emptyPayload() else JSONObject(baseFile.readText(Charsets.UTF_8))
    }.getOrElse { AccountApiClient.emptyPayload() }

    private fun saveBase(payload: JSONObject) {
        val temp = File(baseFile.parentFile, baseFile.name + ".tmp")
        temp.writeText(payload.toString(), Charsets.UTF_8)
        if (!temp.renameTo(baseFile)) {
            baseFile.writeText(payload.toString(), Charsets.UTF_8)
            temp.delete()
        }
    }

    private fun objects(array: JSONArray?): List<JSONObject> = buildList {
        if (array == null) return@buildList
        for (i in 0 until array.length()) array.optJSONObject(i)?.let { add(JSONObject(it.toString())) }
    }

    private fun objectMap(array: JSONArray?): Map<String, JSONObject> =
        objects(array).associateBy { it.optString("sync_id") }.filterKeys { it.isNotBlank() }

    private fun JSONObject.without(vararg names: String): JSONObject {
        val result = JSONObject(this.toString())
        names.forEach(result::remove)
        return result
    }

    private fun canonical(value: Any?): String = when (value) {
        null, JSONObject.NULL -> "null"
        is JSONObject -> value.keys().asSequence().toList().sorted().joinToString(prefix = "{", postfix = "}") { key ->
            JSONObject.quote(key) + ":" + canonical(value.opt(key))
        }
        is JSONArray -> (0 until value.length()).joinToString(prefix = "[", postfix = "]") { index -> canonical(value.opt(index)) }
        is String -> JSONObject.quote(value)
        is Number, is Boolean -> value.toString()
        else -> JSONObject.quote(value.toString())
    }

    companion object {
        private fun sha256(text: String): String = MessageDigest.getInstance("SHA-256")
            .digest(text.toByteArray(Charsets.UTF_8))
            .joinToString("") { "%02x".format(it) }

        fun collectionIdentity(
            cardId: Long,
            artworkId: Long,
            setCode: String,
            rarity: String,
            condition: String,
            language: String,
        ): String {
            val raw = listOf(
                cardId.toString(),
                artworkId.toString(),
                setCode.trim().uppercase(Locale.ROOT),
                rarity.trim().lowercase(Locale.ROOT),
                condition.trim().lowercase(Locale.ROOT),
                language.trim().lowercase(Locale.ROOT),
            ).joinToString("|")
            return "collection:${sha256(raw)}"
        }

        fun deckIdentity(name: String): String = "deck:${sha256(name.trim().lowercase(Locale.ROOT))}"

        fun deckCardIdentity(deckSyncId: String, cardId: Long, artworkId: Long, setCode: String, section: String): String {
            val raw = listOf(
                deckSyncId,
                cardId.toString(),
                artworkId.toString(),
                setCode.trim().uppercase(Locale.ROOT),
                section.trim().uppercase(Locale.ROOT),
            ).joinToString("|")
            return "deckcard:${sha256(raw)}"
        }

        fun artworkUrl(artworkId: Long): String = if (artworkId > 0L) {
            "https://images.ygoprodeck.com/images/cards/$artworkId.jpg"
        } else ""
    }
}

data class AccountSyncReport(
    val revision: Long,
    val collectionCount: Int,
    val deckCount: Int,
)
