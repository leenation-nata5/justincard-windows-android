package org.yugioh.kartenliste.data.local

import org.yugioh.kartenliste.data.model.SearchFilters
import org.yugioh.kartenliste.data.model.SearchSort
import org.yugioh.kartenliste.util.TextNormalizer

data class SqlQuery(
    val whereClause: String,
    val arguments: List<String>,
    val orderBy: String,
)

object SearchSqlBuilder {
    fun build(filters: SearchFilters): SqlQuery {
        val value = filters.normalized()
        val clauses = mutableListOf<String>()
        val arguments = mutableListOf<String>()

        fun contains(column: String, input: String) {
            val key = TextNormalizer.searchKey(input)
            if (key.isNotBlank()) {
                clauses += "$column LIKE ? ESCAPE '\\'"
                arguments += "%${escapeLike(key)}%"
            }
        }

        contains("c.name_key", value.name)
        contains("c.description_key", value.effectText)
        contains("c.type_key", value.cardType)
        contains("c.frame_type_key", value.frameType)
        contains("c.race_key", value.race)
        contains("c.attribute_key", value.attribute)
        contains("c.archetype_key", value.archetype)

        if (value.passcode.isNotBlank()) {
            clauses += "CAST(c.card_id AS TEXT) = ?"
            arguments += value.passcode
        }
        if (value.language != "all") {
            clauses += "c.language = ?"
            arguments += value.language
        }
        if (value.setQuery.isNotBlank()) {
            val signature = TextNormalizer.setCodeSignature(value.setQuery).lowercase()
            val setName = TextNormalizer.searchKey(value.setQuery)
            clauses += """EXISTS (
                SELECT 1 FROM card_prints p
                WHERE p.card_id = c.card_id
                  AND (p.set_code_key LIKE ? ESCAPE '\\' OR p.set_name_key LIKE ? ESCAPE '\\')
            )""".trimIndent()
            arguments += "%${escapeLike(signature)}%"
            arguments += "%${escapeLike(setName)}%"
        }
        if (value.rarity.isNotBlank()) {
            clauses += """EXISTS (
                SELECT 1 FROM card_prints p
                WHERE p.card_id = c.card_id AND p.rarity_key LIKE ? ESCAPE '\\'
            )""".trimIndent()
            arguments += "%${escapeLike(TextNormalizer.searchKey(value.rarity))}%"
        }
        if (value.ownedOnly) {
            clauses += """EXISTS (
                SELECT 1 FROM collection_items i
                WHERE i.card_id = c.card_id AND i.quantity > 0 AND i.deleted = 0
            )""".trimIndent()
        }

        range(clauses, arguments, "c.atk", value.atkMin, value.atkMax)
        range(clauses, arguments, "c.def", value.defMin, value.defMax)
        range(clauses, arguments, "COALESCE(c.link_value, c.level)", value.levelMin, value.levelMax)
        range(clauses, arguments, "c.pendulum_scale", value.scaleMin, value.scaleMax)
        decimalRange(clauses, arguments, "COALESCE(c.cardmarket_price, c.tcgplayer_price)", value.priceMin, value.priceMax)

        val order = when (value.sort) {
            SearchSort.NAME -> "c.name_key ASC, c.card_id ASC, c.artwork_id ASC"
            SearchSort.ATTACK_DESC -> "c.atk IS NULL, c.atk DESC, c.name_key ASC"
            SearchSort.DEFENCE_DESC -> "c.def IS NULL, c.def DESC, c.name_key ASC"
            SearchSort.LEVEL_DESC -> "COALESCE(c.link_value, c.level) IS NULL, COALESCE(c.link_value, c.level) DESC, c.name_key ASC"
            SearchSort.NEWEST -> "c.updated_at DESC, c.name_key ASC"
        }
        return SqlQuery(
            whereClause = clauses.joinToString(" AND ").ifBlank { "1 = 1" },
            arguments = arguments,
            orderBy = order,
        )
    }

    private fun range(
        clauses: MutableList<String>,
        arguments: MutableList<String>,
        column: String,
        minimum: Int?,
        maximum: Int?,
    ) {
        minimum?.let {
            clauses += "$column >= ?"
            arguments += it.toString()
        }
        maximum?.let {
            clauses += "$column <= ?"
            arguments += it.toString()
        }
    }

    private fun decimalRange(
        clauses: MutableList<String>,
        arguments: MutableList<String>,
        column: String,
        minimum: Double?,
        maximum: Double?,
    ) {
        minimum?.let {
            clauses += "$column >= ?"
            arguments += it.toString()
        }
        maximum?.let {
            clauses += "$column <= ?"
            arguments += it.toString()
        }
    }

    private fun escapeLike(value: String): String = value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
}
