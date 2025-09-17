import streamlit as st
import pandas as pd 
import plotly.express as px
import plotly.io as pio
from io import BytesIO
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.lib import colors as rl_colors
from datetime import datetime
from pages.Faculty.faculty_data_helper import get_dataframe_grades, get_semesters_list, compute_subject_failure_rates


current_faculty = st.session_state.get('user_data', {}).get('Name', '')

# --- Session State ---
def initialize_session_state():
    """Initialize session state variables for tab 3"""
    if 'tab3_data_loaded' not in st.session_state:
        st.session_state.tab3_data_loaded = False
    if 'tab3_failure_data' not in st.session_state:
        st.session_state.tab3_failure_data = pd.DataFrame()
    if 'tab3_last_params' not in st.session_state:
        st.session_state.tab3_last_params = {}


def create_summary_table(df):
    """Create summary table aggregating all sections per subject, with Difficulty Level"""
    if df.empty:
        return pd.DataFrame(), {
            "total_subjects": 0,
            "avg_failure_rate": 0,
            "highest_failure_rate": 0,
            "total_students": 0
        }
    
    # Group by subject only
    summary = df.groupby(['SubjectCode', 'Description']).agg({
        'total': 'sum',
        'failures': 'sum',
        'dropouts':'sum'
    }).reset_index()
    
    # Compute failure rate
    summary['fail_rate'] = (summary['failures'] / summary['total'] * 100).round(1)
    summary['dropout_rate'] = (summary['dropouts'] / summary['total'] * 100).round(1)
    
    # Add difficulty level based on failure rate
    def get_difficulty(rate):
        if rate >= 50:
            return "High"
        elif rate >= 20:
            return "Medium"
        else:
            return "Low"
    
    summary['Difficulty Level'] = summary['fail_rate'].apply(get_difficulty)
    
    # Rename for display
    summary = summary.rename(columns={
        'SubjectCode': 'Subject Code',
        'total': 'Total Students',
        'failures': 'Total Failures',
        'fail_rate': 'Failure Rate',
        'dropout_rate': 'Dropout Rate'
    })
    
    # Convert for nice display
    summary['Failure Rate'] = summary['Failure Rate'].astype(str) + '%'
    summary['Dropout Rate'] = summary['Dropout Rate'].astype(str) + '%'
    summary['Total Students'] = summary['Total Students'].astype(str)
    summary['Total Failures'] = summary['Total Failures'].astype(str)
    
    # Metrics
    metrics = {
        "total_subjects": len(summary),
        "avg_failure_rate": df['fail_rate'].mean().round(1),
        "highest_failure_rate": df['fail_rate'].max().round(1),
        "total_students": df['total'].sum()
    }
    
    return summary[['Subject Code', 'Description', 'Total Students', 'Total Failures', 'Failure Rate', 'Dropout Rate', 'Difficulty Level']], metrics


def create_subject_section_data(df):
    """Return per-subject breakdown across sections with Difficulty Level"""
    if df.empty:
        return {}
    
    subject_groups = {}
    
    for code, group in df.groupby('SubjectCode'):
        group_display = group.copy()
        
        # Build section label as "SubjectCode-Section"
        group_display['Section'] = group_display['SubjectCode'] + group_display['section'].astype(str)
        
        # Add Difficulty Level
        def get_difficulty(rate):
            if rate >= 50:
                return "High"
            elif rate >= 20:
                return "Medium"
            else:
                return "Low"
        
        group_display['Difficulty Level'] = group_display['fail_rate'].apply(get_difficulty)
        
        # Rename columns for display
        group_display = group_display.rename(columns={
            'total': 'Total Students',
            'failures': 'Total Failures',
            'fail_rate': 'Failure Rate',
            'dropout_rate': 'Dropout Rate',
        })
        
        # Format values
        group_display['Failure Rate'] = group_display['Failure Rate'].astype(str) + '%'
        group_display['Dropout Rate'] = group_display['Dropout Rate'].astype(str) + '%'
        group_display['Total Students'] = group_display['Total Students'].astype(str)
        group_display['Total Failures'] = group_display['Total Failures'].astype(str)
        
        # Subject name
        subject_name = group_display['Description'].iloc[0] if 'Description' in group_display else ""
        
        # Store cleaned dataframe
        subject_groups[f"{code} - {subject_name}"] = group_display[
            ['Section', 'Total Students', 'Total Failures', 'Failure Rate', 'Dropout Rate', 'Difficulty Level']
        ]
    
    return subject_groups

# ------------------- DISPLAY -------------------
def display_failure_rates(df):
    """Show summary + detailed breakdown"""
    # Summary
    
    summary_table, metrics = create_summary_table(df)

    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total Subjects", metrics["total_subjects"])
    with col2: st.metric("Avg Failure Rate", f"{metrics['avg_failure_rate']:.1f}%")
    with col3: st.metric("Highest Failure Rate", f"{metrics['highest_failure_rate']:.1f}%")
    with col4: st.metric("Total Students", metrics["total_students"])

    # Display summary table
    st.subheader("📊 Summary Failure Rates (All Sections Combined)")
    st.dataframe(summary_table, use_container_width=True, hide_index=True)
    
    # Chart
    st.subheader("📈 Failure Rate Visualization")
    summary_table["Label"] = summary_table["Subject Code"] + " - " + summary_table["Description"]
    summary_table["Failure Rate %"] = summary_table["Failure Rate"].str.replace("%", "").astype(float)
    fig = px.bar(
        summary_table,
        x="Label",
        y="Failure Rate %",
        text="Failure Rate",
        title="Failure Rate per Subject",
        color="Failure Rate %", color_continuous_scale="oranges"
    )
    
    fig.update_yaxes(range=[0, 100])
    fig.update_layout(xaxis_tickangle=-25, showlegend=False)
    fig.update_traces(textposition='outside')
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed breakdown
    st.subheader("📂 Detailed Breakdown by Subject & Section")
    section_data = create_subject_section_data(df)
    for subject_label, subject_df in section_data.items():
        with st.expander(subject_label):
            st.dataframe(subject_df, use_container_width=True, hide_index=True)
            # Chart
            st.subheader("📈 Failure Rate Visualization")
            subject_df["Label"] = subject_df["Section"]
            subject_df["Failure Rate %"] = subject_df["Failure Rate"].str.replace("%", "").astype(float)
            fig2 = px.bar(
                subject_df,
                x="Label",
                y="Failure Rate %",
                text="Failure Rate",
                title="Failure Rate per Subject",
                color="Failure Rate %", color_continuous_scale="oranges"
            )
            fig2.update_yaxes(range=[0, 100])
            fig2.update_layout(xaxis_tickangle=-25, showlegend=False)
            fig2.update_traces(textposition='outside')
            st.plotly_chart(fig2, use_container_width=True)


# --- Data Loader ---
def load_failure_data(new_curriculum, passing_grade, selected_semester_id):
    with st.spinner("Loading failure rate data..."):
        grades_df = get_dataframe_grades(new_curriculum)
        df = compute_subject_failure_rates(
            df=grades_df, 
            new_curriculum=new_curriculum, 
            current_faculty=current_faculty,
            passing_grade=passing_grade, 
            selected_semester_id=selected_semester_id
        )
        return df

def params_changed(new_curriculum, passing_grade, selected_semester_id):
    current_params = {
        'new_curriculum': new_curriculum,
        'passing_grade': passing_grade,
        'selected_semester_id': selected_semester_id
    }
    return st.session_state.tab3_last_params != current_params

# --- Tab Display ---
def show_faculty_tab3_info(new_curriculum):
    initialize_session_state()
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    semesters = get_semesters_list(new_curriculum)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters] + [" - All Semesters - "]
        selected_semester_display = st.selectbox("📅 Select Semester", semester_options, key="tab3_main_semester")
    with col2:
        passing_grade = st.number_input("Passing Grade", 20, 100, 75, key="tab3_passing_grade")
    
    if not st.session_state.tab3_data_loaded:
        st.info("👆 Select your filters and click 'Load Data' to display Data.")
    
    selected_semester_id = None
    if selected_semester_display != " - All Semesters - ":
        for sem in semesters:
            if f"{sem['Semester']} - {sem['SchoolYear']}" == selected_semester_display:
                selected_semester_id = sem['_id']
                break
    
    load_button = st.button("🔄 Load Data", key="tab3_load_button", type="secondary") 
    if load_button:
        with st.spinner("Loading data..."):
            try:
                st.session_state.tab3_new_curriculum = new_curriculum
                st.session_state.tab3_last_params = {
                    'new_curriculum': new_curriculum,
                    'passing_grade': passing_grade,
                    'selected_semester_id': selected_semester_id
                }
                
                df = load_failure_data(new_curriculum, passing_grade, selected_semester_id)
                st.session_state.tab3_failure_data = df
                st.session_state.tab3_data_loaded = True
                
                st.divider()
                st.markdown(f"<h3>👨‍🏫 {current_faculty} Subject Difficulty Heatmap ({selected_semester_display})</h3>", unsafe_allow_html=True)
                
                if df.empty:
                    st.warning("No data available for the selected parameters.")
                    return
                
                # Prepare table
                table_df = df.copy()
                table_df["Failure Rate"] = table_df["fail_rate"].astype(str) + "%"
                table_df["Units"] = table_df["Units"].astype(str)
                table_df["Total Students"] = table_df["total"].astype(str)
                table_df["Total Failures"] = table_df["failures"].astype(str)

                table_df = table_df.rename(columns={"SubjectCode": "Subject Code"})
                # display_cols = ["Subject Code", "Description", "Units", "Total Students", "Total Failures", "Failure Rate"]
                
                
                
                df = load_failure_data(new_curriculum, passing_grade, selected_semester_id)
                display_failure_rates(df)
                
                
                
                # --- PDF Export ---
                st.subheader("📄 Export Report")
                add_pdf_download_button(df, new_curriculum, selected_semester_display, passing_grade)
            
            except Exception as e:
                st.error(f"❌ Error loading data: {str(e)}")

# --- PDF Export ---
def add_pdf_download_button(df, new_curriculum, selected_semester_display=None, passing_grade=None):
    if df is None or df.empty:
        st.warning("No data available to export to PDF.")
        return
    try:
        summary_df, summary_metrics = create_summary_table(df)

        pdf_bytes = generate_failure_pdf(summary_df,df, summary_metrics,  selected_semester_display, passing_grade)
        filename = f"Subject_Difficulty_{'New' if new_curriculum else 'Old'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        st.download_button("📄 Download PDF Report", data=pdf_bytes, file_name=filename, mime="application/pdf")
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")

def style_failure_table(df):
    return df.style.apply(
        lambda row: [
            "color: orange; font-weight: bold" if col in ["Total Failures", "Failure Rate"] else ""
            for col in df.columns
        ],
        axis=1
    )

def generate_failure_pdf(summary_df,detail_df, summary_metrics, selected_semester_display=None, passing_grade=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30, alignment=TA_CENTER, textColor=colors.darkblue)

    # Title and Header Info
    elements.append(Paragraph("Faculty Failure Rate Report", title_style))
    elements.append(Paragraph(f"<b>Faculty:</b> {current_faculty}", styles['Normal']))
    if selected_semester_display:
        elements.append(Paragraph(f"<b>Semester:</b> {selected_semester_display}", styles['Normal']))
    if passing_grade:
        elements.append(Paragraph(f"<b>Passing Grade:</b> {passing_grade}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # --- Summary Metrics ---
    summary_data = [
        ["Total Subjects", "Avg Failure Rate", "Highest Failure Rate", "Total Students"],
        [summary_metrics["total_subjects"], f"{summary_metrics['avg_failure_rate']:.1f}%", f"{summary_metrics['highest_failure_rate']:.1f}%", summary_metrics["total_students"]]
    ]
    summary_metrics_table = Table(summary_data, hAlign="LEFT")
    summary_metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2a654")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10)
    ]))
    elements.append(summary_metrics_table)
    elements.append(Spacer(1, 20))

    # --- Summary Table (All Sections Combined) ---
    elements.append(Paragraph("📊 Summary Failure Rates (All Sections Combined)", styles["Heading2"]))
    if not summary_df.empty:
        table_data = [summary_df.columns.tolist()] + summary_df.values.tolist()
        wrapped = [[Paragraph(str(c), styles["Normal"]) for c in row] for row in table_data]
        summary_detail_table = Table(wrapped, repeatRows=1)
        summary_detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4b8bbe")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9)
        ]))
        elements.append(summary_detail_table)
        elements.append(Spacer(1, 20))

    # --- Chart Visualization ---
    elements.append(Paragraph("📈 Failure Rate Visualization", styles["Heading2"]))
    if not summary_df.empty:
        # Create chart data from summary table
        chart_data = [float(row["Failure Rate"].replace('%', '')) for _, row in summary_df.iterrows()]
        labels = [f"{row['Subject Code']}" for _, row in summary_df.iterrows()]
        
        # Truncate labels if too long for better display
        labels = [label[:8] + "..." if len(label) > 8 else label for label in labels]
        
        drawing = Drawing(700, 400)
        chart = VerticalBarChart()
        chart.x, chart.y, chart.width, chart.height = 50, 50, 600, 300
        chart.data = [chart_data]
        chart.categoryAxis.categoryNames = labels
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max(chart_data) + 10 if chart_data else 100
        chart.valueAxis.valueStep = 10
        chart.bars.fillColor = rl_colors.HexColor("#ff6b6b")
        chart.categoryAxis.labels.angle = -25  # Rotate labels like in the Plotly chart
        chart.categoryAxis.labels.fontSize = 8
        drawing.add(chart)
        drawing.add(String(350, 370, "Subject Failure Rates", fontSize=14, textAnchor='middle'))
        # 🔹 Add percentage labels above bars
        for i, value in enumerate(chart_data):
            x = chart.x + chart.width / len(chart_data) * (i + 0.5)   # center of each bar
            y = chart.y + (value / chart.valueAxis.valueMax) * chart.height + 5
            drawing.add(String(x, y, f"{value:.1f}%", fontSize=8, textAnchor="middle"))
        elements.append(drawing)
        elements.append(Spacer(1, 20))
        section_data = create_subject_section_data(detail_df)
        
        if not summary_df.empty:
            elements.append(Paragraph("🔍 Key Insights", styles["Heading2"]))
            df_calc = summary_df.copy()
            df_calc['failure_rate_float'] = df_calc['Failure Rate'].str.replace('%', '').astype(float)
            
            high = df_calc.loc[df_calc['failure_rate_float'].idxmax()]
            low = df_calc.loc[df_calc['failure_rate_float'].idxmin()]
            
            # Count subjects by difficulty level
            difficulty_counts = summary_df['Difficulty Level'].value_counts()
            
            insights_text = [
                f"• Highest failure rate: {high['Subject Code']} - {high['Description']} ({high['Failure Rate']})",
                f"• Lowest failure rate: {low['Subject Code']} - {low['Description']} ({low['Failure Rate']})",
                f"• High difficulty subjects: {difficulty_counts.get('High', 0)}",
                f"• Medium difficulty subjects: {difficulty_counts.get('Medium', 0)}",
                f"• Low difficulty subjects: {difficulty_counts.get('Low', 0)}"
            ]
            
            for insight in insights_text:
                elements.append(Paragraph(insight, styles['Normal']))
                elements.append(Spacer(1, 6))
            
        
        for subject_label, subject_df in section_data.items():
            
            if subject_df is not None and not subject_df.empty:
                # Add subject header
                elements.append(Paragraph(f"Subject: {subject_label}", styles["Heading3"]))

                # Build the table
                table_data = [subject_df.columns.tolist()] + subject_df.values.tolist()
                wrapped = [[Paragraph(str(c), styles["Normal"]) for c in row] for row in table_data]
                summary_detail_table = Table(wrapped, repeatRows=1)
                summary_detail_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4b8bbe")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9)
                ]))
                elements.append(summary_detail_table)
                elements.append(Spacer(1, 20))

                chart_data = [float(row["Failure Rate"].replace('%', '')) for _, row in subject_df.iterrows()]
                labels = [f"{row['Section']}" for _, row in subject_df.iterrows()]
                
                # Truncate labels if too long for better display
                labels = [label[:8] + "..." if len(label) > 8 else label for label in labels]
                
                drawing = Drawing(700, 400)
                chart = VerticalBarChart()
                chart.x, chart.y, chart.width, chart.height = 50, 50, 600, 300
                chart.data = [chart_data]
                chart.categoryAxis.categoryNames = labels
                chart.valueAxis.valueMin = 0
                chart.valueAxis.valueMax = max(chart_data) + 10 if chart_data else 100
                chart.valueAxis.valueStep = 10
                chart.bars[0].fillColor = rl_colors.HexColor("#ff6b6b")
                chart.categoryAxis.labels.angle = -25  # Rotate labels like in the Plotly chart
                chart.categoryAxis.labels.fontSize = 8
                drawing.add(chart)
                drawing.add(String(350, 370, "Subject Failure Rates", fontSize=14, textAnchor='middle'))
                # 🔹 Add percentage labels above bars
                for i, value in enumerate(chart_data):
                    x = chart.x + chart.width / len(chart_data) * (i + 0.5)   # center of each bar
                    y = chart.y + (value / chart.valueAxis.valueMax) * chart.height + 5
                    drawing.add(String(x, y, f"{value:.1f}%", fontSize=8, textAnchor="middle"))
                elements.append(drawing)
                elements.append(Spacer(1, 20))
                
                # --- Key Insights ---
            if not subject_df.empty:
                elements.append(Paragraph("🔍 Key Insights", styles["Heading2"]))
                df_calc = subject_df.copy()
                df_calc['failure_rate_float'] = df_calc['Failure Rate'].str.replace('%', '').astype(float)
                
                high = df_calc.loc[df_calc['failure_rate_float'].idxmax()]
                low = df_calc.loc[df_calc['failure_rate_float'].idxmin()]
                
                # Count subjects by difficulty level
                difficulty_counts = subject_df['Difficulty Level'].value_counts()
                
                insights_text = [
                    f"• Highest failure rate: {high['Section']} ({high['Failure Rate']})",
                    f"• Lowest failure rate: {low['Section']} ({low['Failure Rate']})",
                    f"• High difficulty subjects: {difficulty_counts.get('High', 0)}",
                    f"• Medium difficulty subjects: {difficulty_counts.get('Medium', 0)}",
                    f"• Low difficulty subjects: {difficulty_counts.get('Low', 0)}"
                ]
                
                for insight in insights_text:
                    elements.append(Paragraph(insight, styles['Normal']))
                    elements.append(Spacer(1, 6))

    

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()