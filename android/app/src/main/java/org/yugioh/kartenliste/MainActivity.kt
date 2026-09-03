package org.yugioh.kartenliste

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.viewmodel.compose.viewModel
import org.yugioh.kartenliste.ui.JustInCardApp
import org.yugioh.kartenliste.ui.JustInCardViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val vm: JustInCardViewModel = viewModel()
            JustInCardApp(vm)
        }
    }
}
