import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import openai
import plotly.io as pio
import json
pio.kaleido.scope.default_format = "png"

color_sequence = px.colors.qualitative.Set2
st.set_page_config(layout="wide")

# 대시보드 제목
st.markdown(
    """
    <h1 style='text-align:center; margin-bottom:10px;'>
        ⚙️ Smart Manufacturing Dashboard ⚙️
    </h1>
    """,
    unsafe_allow_html=True
)

# 스타일 정의
st.sidebar.markdown(
    """
    <style>
    .sidebar-title {
        font-size: 20px;
        font-weight: bold;
        color: #333;
    }
    .sidebar-label {
        font-size: 16px !important;
        font-weight: 600;
        display: block;
        color: #000;
    }
    /* 날짜 범위 입력 필드 글씨 크게 */
    div[data-baseweb="datepicker"] input {
        font-size: 16px !important;
        font-weight: 500 !important;
        padding: 16px !important;
    }
    </style>
    <div class='sidebar-title'>🔧 필터 설정</div>
    """,
    unsafe_allow_html=True
)
st.sidebar.markdown(' ')

# 데이터 로드
@st.cache_data
def load_data():
    df = pd.read_csv("smart_manufacturing_data.csv", parse_dates=["timestamp"])
    df['date_only'] = df['timestamp'].dt.date
    df['time_only'] = df['timestamp'].dt.time
    return df

df = load_data()

# 필터 구성
if 'machine_id' in df.columns:
    machine_list = sorted(df['machine_id'].unique())
    selected_machine = st.sidebar.selectbox("🏭 설비 선택", machine_list)
    df = df[df['machine_id'] == selected_machine]

st.sidebar.markdown(' ')

available_dates = sorted(df['date_only'].unique())
selected_dates = st.sidebar.date_input(
    "📅 날짜 범위 선택",
    value=(available_dates[0], available_dates[-1]),
    min_value=available_dates[0],
    max_value=available_dates[-1]
)
st.sidebar.markdown(' ')

start_time, end_time = st.sidebar.slider(
    "⏰ 시간 범위 선택",
    value=(datetime.time(0, 0), datetime.time(23, 59)),
    format="HH:mm"
)
st.sidebar.markdown(' ')

# 필터 적용
start_date, end_date = selected_dates
df = df[
    (df['date_only'] >= start_date) &
    (df['date_only'] <= end_date) &
    (df['time_only'] >= start_time) &
    (df['time_only'] <= end_time)
]

# 필터 정보 시각화
st.markdown(
    f"""
    <div style="margin-top:-5px; margin-bottom:30px; color: #333; text-align:center;">
        <b>선택한 설비:</b> {selected_machine} &nbsp;&nbsp; | &nbsp;&nbsp;
        <b>날짜:</b> {start_date} ~ {end_date} &nbsp;&nbsp; | &nbsp;&nbsp;
        <b>시간:</b> {start_time.strftime('%H:%M')} ~ {end_time.strftime('%H:%M')}
    </div>
    """,
    unsafe_allow_html=True
)

# KPI 카드 표시
metrics = ['energy_consumption', 'humidity', 'pressure', 'temperature', 'vibration']
icon_dict = {
    'energy_consumption': '⚡',
    'humidity': '💧',
    'pressure': '🌀',    # 압력 → 소용돌이
    'temperature': '🌡️',
    'vibration': '💥'    # 진동 → 진동 모드
}

df_sorted = df.sort_values(by="timestamp")
kpi_cols = st.columns(len(metrics))

for i, metric in enumerate(metrics):
    with kpi_cols[i]:
        if metric in df_sorted.columns and not df_sorted[metric].dropna().empty:
            last_value = round(df_sorted[metric].dropna().iloc[-1], 2)
            icon = icon_dict.get(metric, '')
            st.markdown(
                f"""
                <div style="border:2px solid #ccc; border-radius:12px; padding:10px 5px;
                            text-align:center; background-color:#f9f9f9;">
                    <div style="font-weight:bold;">
                        {icon} {metric.replace('_', ' ').title()}
                    </div>
                    <div style="color:#2c3e50;">
                        {last_value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            st.warning(f"{metric} 없음")

st.markdown("---")


# Bar + Pie
col1, col2 = st.columns([2, 1])  # 비율 살짝 수정

with col1:
    with st.container(border=True):  # ✅ 테두리 추가
        if 'timestamp' in df.columns and 'maintenance_required' in df.columns:
            full_df = load_data()
            full_df = full_df[full_df['machine_id'] == selected_machine]
            full_df = full_df.sort_values(by='timestamp').reset_index(drop=True)
            start_datetime = datetime.datetime.combine(start_date, start_time)
            end_datetime = datetime.datetime.combine(end_date, end_time)
            full_df['datetime'] = full_df['timestamp']
            full_df['in_range'] = full_df['datetime'].between(start_datetime, end_datetime)
            full_df['diff_minutes'] = 0
            last_ts = None
            last_status = None

            for i in range(len(full_df)):
                row = full_df.iloc[i]
                now = row['timestamp']
                status = row['maintenance_required']
                in_range = row['in_range']

                if status == 1 and last_status == 0 and last_ts is not None and in_range:
                    diff = (now - last_ts).total_seconds() / 60
                    full_df.loc[i, 'diff_minutes'] = diff
                elif status == 0 and last_ts is not None and in_range:
                    diff = (now - last_ts).total_seconds() / 60
                    full_df.loc[i, 'diff_minutes'] = diff

                if status == 0 and in_range:
                    last_ts = now
                last_status = status

            full_df['failure_type'] = full_df.get('failure_type', 'Normal').fillna('Normal')
            filtered_df = full_df[full_df['in_range']]
            bar_data = filtered_df.groupby(['maintenance_required', 'failure_type'])['diff_minutes'].sum().reset_index()

            # ✅ 0,1 → 정비 불필요 / 정비 필요로 라벨 변경
            bar_data['maintenance_required'] = bar_data['maintenance_required'].map({
                0: '정비 불필요',
                1: '정비 필요'
            })

            fig_bar = px.bar(
                bar_data,
                x='maintenance_required',
                y='diff_minutes',
                color='failure_type',
                text='diff_minutes',
                title='정비 필요 유무별 소모 시간(분)',
                labels={
                    'maintenance_required': '정비 필요 유무',
                    'failure_type': '고장 유형',
                    'diff_minutes': '누적 시간 (분)'
                },
                color_discrete_sequence=color_sequence
            )

            fig_bar.update_layout(
                barmode='stack',

                xaxis=dict(
                    title='정비 필요 유무',
                ),
                yaxis=dict(
                    title='누적 시간 (분)',
                    tickformat=',d'  # ✅ y축 숫자에 천 단위 쉼표 표시
                ),

                legend=dict(font=dict(size=16))
            )

            fig_bar.update_traces(
                texttemplate='%{text:.0f}',
                textposition='outside'
            )

            st.plotly_chart(fig_bar, use_container_width=True)



with col2:
    with st.container(border=True):  # ✅ 테두리 추가
        if 'maintenance_required' in df.columns:
            df_pie = df.copy()
            df_pie['failure_type'] = df_pie.get('failure_type', 'Normal').fillna('Normal')
            df_pie['Status'] = df_pie.apply(
                lambda row: f'정비 필요 - {row["failure_type"]}' if row['maintenance_required'] == 1 else f'정비 불필요 - {row["failure_type"]}',
                axis=1
            )
            pie_data = df_pie['Status'].value_counts().reset_index()
            pie_data.columns = ['Status', 'Count']

            fig_pie = px.pie(
                pie_data,
                names='Status',
                values='Count',
                title='정비 여부 및 고장 유형별 비율',
                color_discrete_sequence=color_sequence
            )

            st.plotly_chart(fig_pie, use_container_width=True)



st.markdown("---")


# 산점도 + 게이지
col_dot, col_gauge = st.columns([2,1])

with col_dot:
    with st.container(border=True):  # ✅ 테두리 추가
        if 'timestamp' in df.columns and 'maintenance_required' in df.columns:
            dot_df = df.copy()
            dot_df['failure_type'] = dot_df.get('failure_type', 'Normal').fillna('Normal')

            fig_dot = px.scatter(
                dot_df,
                x='timestamp',
                y='maintenance_required',
                color='failure_type',
                title='날짜 및 시간에 따른 유지 보수',
                labels={
                    'timestamp': '시간',
                    'maintenance_required': '정비 여부',
                    'failure_type': '고장 유형'
                },
                color_discrete_sequence=color_sequence
            )

            fig_dot.update_traces(marker=dict(size=10, symbol="diamond"))

            fig_dot.update_layout(
                xaxis=dict(
                    title='날짜',
                    tickformat='%Y-%m-%d'
                ),
                yaxis=dict(
                    title='정비 여부',
                    tickvals=[0, 1],
                    ticktext=['정상 (0)', '정비 필요 (1)']
                ),
            )

            st.plotly_chart(fig_dot, use_container_width=True)



with col_gauge:
    with st.container(border=True):  # ✅ 테두리 추가
        if 'predicted_remaining_life' in df_sorted.columns and not df_sorted['predicted_remaining_life'].dropna().empty:
            last_life = df_sorted['predicted_remaining_life'].dropna().iloc[-1]
            bar_color = "red" if last_life <= 100 else "limegreen"

            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=last_life,
                gauge={
                    'axis': {
                        'range': [0, 500],
                    },
                    "bar": {"color": bar_color, "thickness": 1.0}
                }
            ))

            fig_gauge.update_layout(
                title=dict(
                    text="잔존수명",
                    x=0.0,
                    xanchor='left',
                    yanchor='top'
                ),
                margin=dict(t=70)
            )

            st.plotly_chart(fig_gauge, use_container_width=True)

summary_dot = {
    "정비 필요 건수": int(dot_df["maintenance_required"].sum()),
    "총 샘플 수": int(len(dot_df)),
    "고장 유형별 분포": dot_df["failure_type"].value_counts().to_dict(),
    "고장 발생 시간" : dot_df[dot_df['maintenance_required'] == 1]['timestamp'].to_dict()
}

report_data = {
    'machine': selected_machine,
    'date': f"{start_date} ~ {end_date}",
    'time': f"{start_time.strftime('%H:%M')} ~ {end_time.strftime('%H:%M')}",
    "chart_data" : {
        '정비 필요 유무별 소모 시간(분)' : bar_data[['maintenance_required', 'failure_type', 'diff_minutes']].to_dict(orient="records"),
        '정비 여부 및 고장 유형별 비율' : pie_data.to_dict(orient="records"),
        '날짜 및 시간에 따른 유지 보수' : summary_dot,
        '잔존수명' : last_life
    }
}


report_data_str = json.dumps(report_data, indent=2, default=str)

# ✅ GPT 보고서 생성 버튼
st.markdown("---")
st.markdown(
    "<h2 style='font-size:25px;'>📄 시각화 기반 자동 보고서 생성</h2>",
    unsafe_allow_html=True
)

import openai
import plotly.io as pio
pio.kaleido.scope.default_format = "png"

# 🔐 사용자 API 키 입력
user_api_key = st.sidebar.text_input("🔑 OpenAI API 키 입력", type="password")
st.sidebar.markdown(' ')

# GPT 보고서 생성 버튼
if st.sidebar.button("🧠 보고서 생성 요청"):
    if not user_api_key:
        st.error("❗ OpenAI API 키를 입력해주세요.")
    else:
        try:
            fig_bar.write_image("graph_bar.png")
            fig_pie.write_image("graph_pie.png")
            fig_dot.write_image("graph_dot.png")
            fig_gauge.write_image("graph_gauge.png")

            prompt = f"""
            ### 🔍 분석 개요
선택된 설비의 정비 필요 상태, 고장 유형, 예측 잔여 수명 등 운영 이력 데이터를 기반으로 실무자가 이해할 수 있는 마크다운 보고서를 작성해 주세요. 각 시각화는 실제 설비 유지보수 판단 및 사전 대응에 활용됩니다.

# 보고서 생성에 필요한 원본 데이터 (JSON 형태)
{report_data_str}

각 시각화 결과는 아래 이미지 파일로 첨부되어 있습니다.

1. **정비 필요 유무별 소모 시간(분)**: graph_bar.png
2. **정비 여부 및 고장 유형 비율**: graph_pie.png
3. **잔존 수명 게이지**: graph_gauge.png
4. **날짜에 따른 유지보수 산점도**: graph_dot.png

---

보고서 제목 : 설비 유지보수 분석 보고서

아래 세가지 정보를 필수로 보고서 제목 아래에 배치해줘
**설비:** machine
**날짜 범위:** date
**시간 범위:** time('%H:%M')

---

### 1. 유지 보수별 소모 시간 (Bar Chart)
- **분석 목적:** 설비의 누적 운전 시간 대비 정비 필요 여부와 고장 유형별 시간 분포 파악
- **실무자 질문 예시:** "고장이 자주 발생하는 유형은 무엇인가요?", "정비 필요 시간은 정상 운전 시간에 비해 얼마나 되나요?", "정비 필요한 상태가 얼마나 지속되었는가?", "특정 고장이 얼마나 집중되어어 발생하는가?"
- ![](graph_bar.png)
- **요청 내용:** 그래프를 해석하고, 정상 상태와 고장 상태 시간 비중, 고장 유형별 소요 시간 등을 설명해 주세요

---

### 2. 정비 여부 및 고장 유형별 비율 (Pie Chart)
- **분석 목적:** 정비 필요 여부 및 고장 유형의 상대적 비율 파악
- **실무자 질문 예시:** "전체 중 실제 고장 설비는 얼마나 되나요?", "고장이 자주 발생하는 유형은 무엇인가요?", "고장 유형 중 어떤 것이 최근 가장 많이 발생하지?",
- ![](graph_pie.png)
- **요청 내용:** 정상 상태 대비 정비 필요 비율, 그중 실제 고장 유형별 분포를 해석해 주세요

---

### 3. 예측 잔여 수명 게이지 (Gauge)
- **분석 목적:** 예측된 설비 잔여 수명 기반으로 교체 또는 정비 시점 판단(0~500 범위이며, 100 이하는 위험한 상태라 판단)
- **실무자 질문 예시:** "지금 이 설비를 정비해야 하나요?", "예측 수명이 위험 수준인가요?", "최근 센서 수치가 수명에 영향을 줬나?"
- ![](graph_gauge.png)
- **요청 내용:** 잔여 수명 값 해석, 기준 범위와 비교, 대응 필요 여부를 판단할 수 있도록 설명해 주세요

---

### 4. 날짜에 따른 유지보수 발생 시점 (Scatter Plot)
- **분석 목적:** 시간 흐름에 따른 고장 발생 시점과 고장 유형 트렌드 확인
- **실무자 질문 예시:** "최근 고장이 몰려 발생한 시점은 언제인가요?", "반복되는 고장 유형이 있나요?"
- ![](graph_dot.png)
- **요청 내용:** 시간에 따른 정비 필요 발생 분포와 고장 유형 반복 패턴, 정비 집중 구간을 해석해 주세요

---

### 📌 보고서 작성 조건
- 각 그래프에 대해 **시각화 해석 (6~8문장)**, **종합 인사이트 도출 (5문장 이상)**, **운영 개선 제안 (3가지 이상)** 포함
- 형식은 **한글 마크다운 문서**로 작성
- 실무자가 바로 조치를 취할 수 있도록 **직관적이고 실용적인 표현** 사용
- 위의 네가지 시각화 자료를 적절한 위치에 마크다운 문법으로 삽입해줘
- 위의 실무자 질문 예시의 답변만 보고서에 작성해줘
- ```markdown```로 감싸지 마 바로 마크다운 문법으로 작성해줘
"""

            client = openai.OpenAI(api_key=user_api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            report = response.choices[0].message.content
            filename = f"smart_factory_report_{selected_machine}_{start_date}_{end_date}.md"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(report)

            st.success(f"✅ GPT 기반 보고서 생성 완료: {filename}")
            st.download_button("📥 보고서 다운로드 (Markdown)", report, file_name=filename)

        except Exception as e:
            st.error(f"📛 보고서 생성 중 오류 발생: {e}")
