package kr.ac.baekseok.semesh

import android.content.Intent
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

// 가이드 상세 화면: GuideActivity가 보낸 주제 번호로 GuideData에서 내용을 꺼내 화면에 그린다.
class GuideDetailActivity : AppCompatActivity() {

    private lateinit var tvIntro: TextView
    private lateinit var tvProgress: TextView
    private lateinit var tvSource: TextView
    private lateinit var itemContainer: LinearLayout
    private lateinit var btnDetailBack: Button

    private var checkedCount = 0 // 체크리스트에서 체크한 개수

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_guide_detail)

        tvIntro = findViewById(R.id.tvIntro)
        tvProgress = findViewById(R.id.tvProgress)
        tvSource = findViewById(R.id.tvSource)
        itemContainer = findViewById(R.id.itemContainer)
        btnDetailBack = findViewById(R.id.btnDetailBack)

        // 앞 화면에서 putExtra("topic", i)로 보낸 번호 받기 (없으면 0번)
        val index = intent.getIntExtra("topic", 0)
        val topic = GuideData.topics[index]

        title = topic.title
        tvIntro.text = topic.intro
        tvSource.text = "출처: ${topic.source}"

        if (topic.checkable) {
            tvProgress.visibility = android.view.View.VISIBLE
            updateProgress(topic.items.size)
        }

        // 항목 하나씩 화면에 추가
        for (item in topic.items) {
            addItem(item, topic.checkable, topic.items.size)
        }

        btnDetailBack.setOnClickListener {
            finish()
        }
    }//onCreate()

    // 항목 1개 = [제목(또는 체크박스)] + [설명] + [전화 버튼] + [홈페이지 버튼]
    fun addItem(item: GuideItem, checkable: Boolean, total: Int) {
        // ① 제목
        if (checkable) {
            val chk = CheckBox(this)
            chk.text = item.title
            chk.textSize = 16f
            chk.setTypeface(null, Typeface.BOLD)
            chk.setPadding(0, 24, 0, 0)
            // 체크할 때마다 개수를 세서 "n / 13 확인"을 갱신
            chk.setOnCheckedChangeListener { _, isChecked ->
                if (isChecked) checkedCount++ else checkedCount--
                updateProgress(total)
            }
            itemContainer.addView(chk)
        } else {
            val tvTitle = TextView(this)
            tvTitle.text = item.title
            tvTitle.textSize = 17f
            tvTitle.setTypeface(null, Typeface.BOLD)
            tvTitle.setPadding(0, 40, 0, 8)
            itemContainer.addView(tvTitle)
        }

        // ② 설명 (비어 있으면 생략)
        if (item.body.isNotEmpty()) {
            val tvBody = TextView(this)
            tvBody.text = item.body
            tvBody.textSize = 15f
            tvBody.setLineSpacing(0f, 1.2f) // 줄 간격을 조금 넓혀 읽기 쉽게
            itemContainer.addView(tvBody)
        }

        // ③ 전화 버튼: ACTION_DIAL은 전화 앱에 번호만 입력해 줌 (바로 걸지 않아서 권한이 필요 없다)
        if (item.phone != null) {
            val btnCall = Button(this)
            btnCall.text = "전화 걸기 ${item.phone}"
            btnCall.setOnClickListener {
                val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:${item.phone}"))
                startActivity(intent)
            }
            itemContainer.addView(btnCall)
        }

        // ④ 홈페이지 버튼: ACTION_VIEW + 주소 → 휴대폰 기본 브라우저로 열기
        if (item.url != null) {
            val btnWeb = Button(this)
            btnWeb.text = "홈페이지 열기"
            btnWeb.setOnClickListener {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(item.url))
                startActivity(intent)
            }
            itemContainer.addView(btnWeb)
        }
    }

    fun updateProgress(total: Int) {
        tvProgress.text = "$checkedCount / $total 확인"
    }
}//GuideDetailActivity
