package org.yugioh.kartenliste

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.yugioh.kartenliste.data.local.SearchSqlBuilder
import org.yugioh.kartenliste.data.model.SearchFilters
import org.yugioh.kartenliste.data.model.SearchSort

class SearchSqlBuilderTest {
    @Test
    fun combinesAllIndependentFilters() {
        val query = SearchSqlBuilder.build(SearchFilters(
            name = "Drache",
            effectText = "Spezialbeschwörung",
            setQuery = "LOB-DE001",
            rarity = "Ultra Rare",
            attribute = "Licht",
            atkMin = 2500,
            atkMax = 3500,
            priceMax = 100.0,
            ownedOnly = true,
            sort = SearchSort.ATTACK_DESC,
        ))
        assertTrue(query.whereClause.contains("c.name_key"))
        assertTrue(query.whereClause.contains("c.description_key"))
        assertTrue(query.whereClause.contains("card_prints"))
        assertTrue(query.whereClause.contains("collection_items"))
        assertTrue(query.whereClause.contains("c.atk >= ?"))
        assertTrue(query.whereClause.contains("c.atk <= ?"))
        assertTrue(query.whereClause.contains("cardmarket_price"))
        assertEquals("%drache%", query.arguments.first())
        assertTrue(query.orderBy.contains("c.atk DESC"))
    }
}
