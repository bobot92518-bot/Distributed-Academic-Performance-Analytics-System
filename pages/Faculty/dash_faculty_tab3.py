import streamlit as st
import pandas as pd 
import plotly.express as px
import plotly.io as pio
import tempfile
from io import BytesIO
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import inch
from datetime import datetime
from global_utils import pkl_data_to_df, subjects_cache, new_subjects_cache
from pages.Faculty.faculty_data_helper import get_dataframe_grades, get_semesters_list


current_faculty = st.session_state.get('user_data', {}).get('Name', '')

# Initialize session state keys
def initialize_session_state():
    """Initialize session state variables for tab 3"""
    if 'tab3_data_loaded' not in st.session_state:
        st.session_state.tab3_data_loaded = False
    if 'tab3_failure_data' not in st.session_state:
        st.session_state.tab3_failure_data = pd.DataFrame()
    if 'tab3_last_params' not in st.session_state:
        st.session_state.tab3_last_params = {}

@st.cache_data(ttl=300)
def compute_subject_failure_rates(df, new_curriculum, passing_grade: int = 75, selected_semester_id = None):
    """
    Compute failure rates per Teacher + SubjectCode.
    Assumes Grade < passing_grade = failure.
    Only includes subjects handled by the given faculty.
    """
    
    if df.empty:
        return pd.DataFrame()
    
    if selected_semester_id is not None:
        df = df[df["SemesterID"] == selected_semester_id]
    
    subjects_df = pkl_data_to_df(new_subjects_cache if new_curriculum else subjects_cache)

    if subjects_df is None or subjects_df.empty:
        st.warning("Subjects data not available.")
        return pd.DataFrame()

    subjects_df = subjects_df[subjects_df["Teacher"] == current_faculty]
    if subjects_df.empty:
        return pd.DataFrame()

    df["is_fail"] = df["Grade"] < passing_grade

    grouped = df.groupby(["Teacher", "SubjectCode"]).agg(
        total=("StudentID", "count"),
        failures=("is_fail", "sum")
    ).reset_index()

    grouped["fail_rate"] = (grouped["failures"] / grouped["total"] * 100).round(2)
    grouped = grouped[grouped["total"] > 0]

    merged = grouped.merge(
        subjects_df[["_id", "Description", "Units", "Teacher"]],
        left_on="SubjectCode", right_on="_id", how="inner"
    )

    merged = merged.drop(columns=["_id"])
    
    merged = merged.sort_values(
        ["fail_rate", "failures", "total"],
        ascending=[False, False, False]
    )

    return merged

def load_failure_data(new_curriculum, passing_grade, selected_semester_id):
    """Load and cache failure rate data"""
    with st.spinner("Loading failure rate data..."):
        grades_df = get_dataframe_grades(new_curriculum)
        df = compute_subject_failure_rates(
            grades_df, 
            new_curriculum, 
            passing_grade=passing_grade, 
            selected_semester_id=selected_semester_id
        )
        
        # Store in session state
        st.session_state.tab3_failure_data = df
        st.session_state.tab3_data_loaded = True
        st.session_state.tab3_last_params = {
            'new_curriculum': new_curriculum,
            'passing_grade': passing_grade,
            'selected_semester_id': selected_semester_id
        }
        
        return df

def params_changed(new_curriculum, passing_grade, selected_semester_id):
    """Check if parameters have changed since last load"""
    current_params = {
        'new_curriculum': new_curriculum,
        'passing_grade': passing_grade,
        'selected_semester_id': selected_semester_id
    }
    return st.session_state.tab3_last_params != current_params

def show_faculty_tab3_info(new_curriculum):
    # Initialize session state
    initialize_session_state()
    
    current_faculty = st.session_state.get('user_data', {}).get('Name', '')
    semesters = get_semesters_list(new_curriculum)
    
    # Controls row
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        semester_options = [f"{sem['Semester']} - {sem['SchoolYear']}" for sem in semesters] + [" - All Semesters - "]
        selected_semester_display = st.selectbox(
            "📅 Select Semester", 
            semester_options,
            key="tab3_main_semester"
        )
    
    with col2:
        passing_grade = st.number_input("Passing Grade", 20, 100, 75, key="tab3_passing_grade")
    
    load_button = st.button("🔄 Load Data", key="tab3_load_button", type="secondary")
    if not st.session_state.tab3_data_loaded:
        st.info("👆 Select your filters and click 'Load Data' to display Data.")
    
    # Determine selected semester ID
    selected_semester_id = None
    if selected_semester_display != " - All Semesters - ":
        for sem in semesters:
            if f"{sem['Semester']} - {sem['SchoolYear']}" == selected_semester_display:
                selected_semester_id = sem['_id']
                break
    
    # Check if we need to reload data
    should_load = (
        load_button or 
        not st.session_state.tab3_data_loaded or 
        params_changed(new_curriculum, passing_grade, selected_semester_id)
    )
    
    # Load data if needed
    if should_load:
        df = load_failure_data(new_curriculum, passing_grade, selected_semester_id)
    else:
        df = st.session_state.tab3_failure_data
    
    st.divider()
    
    # Header with data status
    data_status = "Current Data" if st.session_state.tab3_data_loaded else "No Data Loaded"
    st.markdown(
        f"<h3 style='text-align: left;'>👨‍🏫 {current_faculty} Subject Difficulty Heatmap ({selected_semester_display}) - {data_status}</h3>",
        unsafe_allow_html=True
    )
    
    # Display results
    if df.empty:
        if st.session_state.tab3_data_loaded:
            st.warning("No data available for the selected parameters.")
        else:
            st.info("Click 'Load Data' to view failure rate analysis.")
        return
    
    # Prepare table data
    table_df = df.copy()
    table_df["Failure Rate"] = table_df["fail_rate"].astype(str) + "%"
    table_df["Units"] = table_df["Units"].astype(str)
    table_df["Total Students"] = table_df["total"].astype(str)
    table_df["Total Failures"] = table_df["failures"].astype(str)

    table_df = table_df.rename(columns={
        "SubjectCode": "Subject Code",
        "Description": "Description"
    })

    display_cols = [
        "Subject Code",
        "Description",
        "Units",
        "Total Students",
        "Total Failures",
        "Failure Rate"
    ]
    
    # Data summary metrics
    col_metrics1, col_metrics2, col_metrics3, col_metrics4 = st.columns(4)
    
    with col_metrics1:
        st.metric("Total Subjects", len(df))
    
    with col_metrics2:
        avg_failure_rate = df["fail_rate"].mean()
        st.metric("Avg Failure Rate", f"{avg_failure_rate:.1f}%")
    
    with col_metrics3:
        highest_failure = df["fail_rate"].max() if not df.empty else 0
        st.metric("Highest Failure Rate", f"{highest_failure:.1f}%")
    
    with col_metrics4:
        total_students_analyzed = df["total"].sum()
        st.metric("Total Students", total_students_analyzed)
    
    # Display table
    st.subheader("📊 Detailed Failure Rate Table")
    st.dataframe(
        style_failure_table(table_df[display_cols]), 
        use_container_width=True, 
        hide_index=True
    )
    
    # Display chart
    st.subheader("📈 Failure Rate Visualization")
    
    # Prepare chart data
    table_df["Label"] = table_df["Subject Code"] + " - " + table_df["Description"]
    table_df["Failure Rate %"] = table_df["Failure Rate"].str.replace("%", "").astype(float)
    
    # Bar chart
    fig = px.bar(
        table_df,
        x="Label",
        y="Failure Rate %",
        text="Failure Rate",
        title="Failure Rate per Subject",
        color="Failure Rate %",
        color_continuous_scale="oranges"
    )

    fig.update_layout(
        xaxis_title="Subject",
        yaxis_title="Failure Rate (%)",
        xaxis_tickangle=-25,
        showlegend=False
    )
    
    fig.update_traces(textposition='outside')

    st.plotly_chart(fig, use_container_width=True)
    
    # Additional insights
    if not df.empty:
        st.subheader("🔍 Key Insights")
        
        # Find subjects with highest and lowest failure rates
        highest_failure_subject = df.loc[df["fail_rate"].idxmax()]
        lowest_failure_subject = df.loc[df["fail_rate"].idxmin()]
        
        insight_col1, insight_col2 = st.columns(2)
        
        with insight_col1:
            st.error(f"**Highest Failure Rate:** {highest_failure_subject['SubjectCode']} - {highest_failure_subject['Description']} ({highest_failure_subject['fail_rate']}%)")
        
        with insight_col2:
            st.success(f"**Lowest Failure Rate:** {lowest_failure_subject['SubjectCode']} - {lowest_failure_subject['Description']} ({lowest_failure_subject['fail_rate']}%)")

    # --- PDF Export Button ---
    st.subheader("📄 Export Report")
    add_pdf_download_button(df, table_df, fig, display_cols, new_curriculum, selected_semester_display, passing_grade)


def add_pdf_download_button(df, table_df, fig, display_cols, new_curriculum, selected_semester_display = None, passing_grade = None):
    """Add a download button for PDF export"""
    
    if df is None or df.empty:
        st.warning("No data available to export to PDF.")
        return
    
    try:
        summary_metrics = {
            "total_subjects": len(df),
            "avg_failure_rate": df["fail_rate"].mean(),
            "highest_failure_rate": df["fail_rate"].max(),
            "total_students": df["total"].sum()
        }

        # Generate PDF (returns bytes now)
        pdf_bytes = generate_failure_pdf(
            table_df[display_cols],
            summary_metrics,
            fig,
            selected_semester_display,
            passing_grade
        )
        
        # Generate filename (always ends with .pdf)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        curriculum_type = "New" if new_curriculum else "Old"
        filename = f"Subject_Difficulty_{curriculum_type}_{timestamp}.pdf"
        
        # Download button
        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            type="secondary",
            help="Download Subjects with Highest Failure Rates",
            key="download_pdf_tab3" 
        )
        
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        st.info("Please ensure all required data is properly loaded before generating the PDF.")

def style_failure_table(df):
    """Style Total Failures and Failure Rate in dark red."""
    return df.style.apply(
        lambda row: [
            "color: orange; font-weight: bold" if col in ["Total Failures", "Failure Rate"] else ""
            for col in df.columns
        ],
        axis=1
    )

# --- PDF Generator ---
def generate_failure_pdf(df, summary_metrics, chart_fig, selected_semester_display = None, passing_grade = None):
    """
    Generate PDF report containing:
    1. Summary metrics
    2. Failure rate table
    3. Chart visualization
    Returns raw PDF bytes for download button.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    styles.add(ParagraphStyle(name="CenterHeading", alignment=1, fontSize=14, spaceAfter=10))

    # --- Title Block ---
    elements.append(Paragraph("Faculty Failure Rate Report", title_style))
    elements.append(Paragraph(f"Faculty: {current_faculty}", styles['Normal']))

    if selected_semester_display:
        elements.append(Paragraph(f"Semester: {selected_semester_display}", styles['Normal']))
    if passing_grade:
        elements.append(Paragraph(f"Passing Grade: {passing_grade}", styles['Normal']))

    elements.append(Spacer(1, 12))

    # --- Summary Metrics Table ---
    summary_data = [
        ["Total Subjects", "Avg Failure Rate", "Highest Failure Rate", "Total Students"],
        [
            summary_metrics["total_subjects"],
            f"{summary_metrics['avg_failure_rate']:.1f}%",
            f"{summary_metrics['highest_failure_rate']:.1f}%",
            summary_metrics["total_students"]
        ]
    ]

    summary_table = Table(summary_data, hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2a654")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # --- Detailed Failure Rate Table ---
    table_data = [df.columns.tolist()] + df.values.tolist()

    wrapped_data = []
    for row in table_data:
        new_row = []
        for idx, cell in enumerate(row):
            if idx == 1 and isinstance(cell, str):  # Description column
                new_row.append(Paragraph(cell, ParagraphStyle("wrap", fontSize=8)))
            else:
                new_row.append(str(cell))
        new_row = [Paragraph(str(c), ParagraphStyle("normal", fontSize=8)) if not isinstance(c, Paragraph) else c for c in new_row]
        wrapped_data.append(new_row)

    detail_table = Table(wrapped_data, repeatRows=1)
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4b8bbe")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    elements.append(Paragraph("Detailed Failure Rate Table", styles["Heading2"]))
    elements.append(detail_table)
    elements.append(Spacer(1, 20))

    # --- Chart (Plotly to PNG then insert) ---
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
        pio.write_image(chart_fig, tmpfile.name, format="png", scale=2, width=900, height=500)
        chart_img = Image(tmpfile.name, width=7*inch, height=4*inch)
        elements.append(Paragraph("Failure Rate Chart", styles["Heading2"]))
        elements.append(chart_img)

    # Build PDF into buffer
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()