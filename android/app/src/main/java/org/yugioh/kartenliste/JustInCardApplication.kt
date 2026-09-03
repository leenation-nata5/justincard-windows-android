package org.yugioh.kartenliste

import android.app.Application
import org.yugioh.kartenliste.data.JustInCardDatabase

class JustInCardApplication : Application() {
    val database by lazy { JustInCardDatabase(this) }
}
