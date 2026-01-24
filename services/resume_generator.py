from docx import Document
from docx.shared import Pt, Inches, RGBColor, Twips
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from datetime import date
import psycopg2
from psycopg2.extras import RealDictCursor
from .database import get_connection
import io

def format_date(date_obj):
    """Format date object to string"""
    if date_obj:
        return date_obj.strftime("%Y")
    return "Present"

def format_date_range(start_date, end_date, is_current=False):
    """Format date range like '2023 - 2026' or '2023 - Present'"""
    start = start_date.strftime("%Y") if start_date else ""
    if is_current:
        end = "Present"
    else:
        end = end_date.strftime("%Y") if end_date else "Present"
    return f"{start} - {end}" if start else end

def add_section_heading(document, text):
    """Add a section heading with bottom border line"""
    para = document.add_paragraph()
    run = para.add_run(text.upper())
    run.font.bold = True
    run.font.size = Pt(12)
    run.font.name = 'Arial'
    run.font.color.rgb = RGBColor(0, 0, 0)

    # Add letter spacing
    rPr = run._element.get_or_add_rPr()
    spacing = OxmlElement('w:spacing')
    spacing.set(qn('w:val'), '40')
    rPr.append(spacing)

    # Add bottom border
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '000000')
    pBdr.append(bottom)
    pPr.append(pBdr)

    para.paragraph_format.space_before = Pt(16)
    para.paragraph_format.space_after = Pt(8)
    return para

def add_entry_header(document, institution, date_range):
    """Add entry header like 'Company Name | 2023 - 2026'"""
    para = document.add_paragraph()

    inst_run = para.add_run(institution)
    inst_run.font.name = 'Arial'
    inst_run.font.size = Pt(10)
    inst_run.font.color.rgb = RGBColor(100, 100, 100)

    sep_run = para.add_run(' | ')
    sep_run.font.name = 'Arial'
    sep_run.font.size = Pt(10)
    sep_run.font.color.rgb = RGBColor(100, 100, 100)

    date_run = para.add_run(date_range)
    date_run.font.name = 'Arial'
    date_run.font.size = Pt(10)
    date_run.font.color.rgb = RGBColor(100, 100, 100)

    para.paragraph_format.space_after = Pt(2)
    para.paragraph_format.space_before = Pt(8)
    return para

def add_entry_title(document, title):
    """Add entry title in bold (like job title or degree)"""
    para = document.add_paragraph()
    run = para.add_run(title)
    run.font.name = 'Arial'
    run.font.size = Pt(11)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0, 0, 0)
    para.paragraph_format.space_after = Pt(4)
    para.paragraph_format.space_before = Pt(0)
    return para

def add_description_text(document, text):
    """Add description paragraph"""
    para = document.add_paragraph()
    run = para.add_run(text)
    run.font.name = 'Arial'
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(60, 60, 60)
    para.paragraph_format.space_after = Pt(8)
    para.paragraph_format.space_before = Pt(0)
    return para

def add_bullet_point(document, text):
    """Add a bullet point item"""
    para = document.add_paragraph()
    # Add bullet character
    bullet_run = para.add_run('• ')
    bullet_run.font.name = 'Arial'
    bullet_run.font.size = Pt(10)

    text_run = para.add_run(text)
    text_run.font.name = 'Arial'
    text_run.font.size = Pt(10)
    text_run.font.color.rgb = RGBColor(60, 60, 60)

    para.paragraph_format.left_indent = Inches(0.25)
    para.paragraph_format.first_line_indent = Inches(-0.15)
    para.paragraph_format.space_after = Pt(2)
    para.paragraph_format.space_before = Pt(0)
    return para


def generate_resume(user_id: int) -> io.BytesIO:
    """
    Generate a DOCX resume for a user in the new clean design
    Returns BytesIO object containing the document
    """

    # Fetch all user data
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Get user info
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            raise ValueError("User not found")

        # Get work experiences
        cursor.execute("""
            SELECT * FROM work_experiences
            WHERE user_id = %s
            ORDER BY is_current DESC, start_date DESC
        """, (user_id,))
        work_experiences = cursor.fetchall()

        # Get education
        cursor.execute("""
            SELECT * FROM education
            WHERE user_id = %s
            ORDER BY end_date DESC NULLS FIRST
        """, (user_id,))
        education = cursor.fetchall()

        # Get skills
        cursor.execute("""
            SELECT * FROM skills
            WHERE user_id = %s
            ORDER BY skill_name ASC
        """, (user_id,))
        skills = cursor.fetchall()

        # Get projects
        cursor.execute("""
            SELECT * FROM projects
            WHERE user_id = %s
            ORDER BY start_date DESC NULLS LAST
        """, (user_id,))
        projects = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    # Create document
    document = Document()

    # Set margins
    sections = document.sections
    for section in sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Set default font
    style = document.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(10)

    # ==================== HEADER - NAME ====================
    name_para = document.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_para.add_run(user['name'].upper())
    name_run.font.size = Pt(28)
    name_run.font.bold = True
    name_run.font.name = 'Arial'
    name_run.font.color.rgb = RGBColor(0, 0, 0)
    name_para.paragraph_format.space_after = Pt(4)
    name_para.paragraph_format.space_before = Pt(0)

    # ==================== PROFESSIONAL TITLE ====================
    if user.get('headline'):
        title_para = document.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.add_run(user['headline'])
        title_run.font.size = Pt(14)
        title_run.font.name = 'Arial'
        title_run.font.color.rgb = RGBColor(60, 60, 60)
        title_para.paragraph_format.space_after = Pt(8)
        title_para.paragraph_format.space_before = Pt(0)

    # ==================== CONTACT INFO ROW ====================
    contact_para = document.add_paragraph()
    contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    contact_items = []

    if user.get('phone'):
        contact_items.append(('phone', user['phone']))
    if user.get('email'):
        contact_items.append(('email', user['email']))
    if user.get('location'):
        contact_items.append(('location', user['location']))

    for i, (icon_type, value) in enumerate(contact_items):
        # Add icon symbol
        if icon_type == 'phone':
            icon = '\u260E '  # Phone symbol
        elif icon_type == 'email':
            icon = '\u2709 '  # Envelope symbol
        elif icon_type == 'location':
            icon = '\u2691 '  # Flag/location symbol
        else:
            icon = ''

        icon_run = contact_para.add_run(icon)
        icon_run.font.name = 'Arial'
        icon_run.font.size = Pt(10)
        icon_run.font.color.rgb = RGBColor(80, 80, 80)

        value_run = contact_para.add_run(value)
        value_run.font.name = 'Arial'
        value_run.font.size = Pt(10)
        value_run.font.color.rgb = RGBColor(80, 80, 80)

        # Add spacing between items
        if i < len(contact_items) - 1:
            spacer = contact_para.add_run('          ')
            spacer.font.size = Pt(10)

    contact_para.paragraph_format.space_after = Pt(12)

    # ==================== ABOUT ME / SUMMARY ====================
    if user.get('summary'):
        add_section_heading(document, 'ABOUT ME')
        add_description_text(document, user['summary'])

    # ==================== EDUCATION ====================
    if education:
        add_section_heading(document, 'EDUCATION')

        for edu in education:
            # Institution | Date Range
            date_range = format_date_range(edu.get('start_date'), edu.get('end_date'))
            add_entry_header(document, edu['school'], date_range)

            # Degree title in bold
            degree_text = edu['degree']
            if edu.get('field_of_study'):
                degree_text += f" in {edu['field_of_study']}"
            add_entry_title(document, degree_text)

            # Description/achievements if available
            if edu.get('description'):
                add_description_text(document, edu['description'])
            elif edu.get('gpa'):
                add_description_text(document, f"GPA: {edu['gpa']}")

    # ==================== WORK EXPERIENCE ====================
    if work_experiences:
        add_section_heading(document, 'WORK EXPERIENCE')

        for work in work_experiences:
            # Company | Date Range
            date_range = format_date_range(work.get('start_date'), work.get('end_date'), work.get('is_current'))
            add_entry_header(document, work['company'], date_range)

            # Job title in bold
            add_entry_title(document, work['title'])

            # Responsibilities
            if work.get('responsibilities'):
                responsibilities = work['responsibilities']
                resp_list = [r.strip() for r in responsibilities.split('\n') if r.strip()]

                if len(resp_list) <= 1 and responsibilities:
                    # Single paragraph description
                    add_description_text(document, responsibilities)
                else:
                    # Multiple bullet points
                    for resp in resp_list:
                        if resp:
                            add_bullet_point(document, resp)

    # ==================== PROJECTS ====================
    if projects:
        add_section_heading(document, 'PROJECTS')

        for project in projects:
            # Project title | Date Range
            date_range = ""
            if project.get('start_date'):
                date_range = format_date_range(project.get('start_date'), project.get('end_date'))
            add_entry_header(document, project['title'], date_range)

            # Technologies as subtitle if available
            if project.get('technologies'):
                tech_para = document.add_paragraph()
                tech_run = tech_para.add_run(f"Technologies: {project['technologies']}")
                tech_run.font.name = 'Arial'
                tech_run.font.size = Pt(9)
                tech_run.font.italic = True
                tech_run.font.color.rgb = RGBColor(100, 100, 100)
                tech_para.paragraph_format.space_after = Pt(4)

            # Description
            if project.get('description'):
                desc_list = [d.strip() for d in project['description'].split('\n') if d.strip()]

                if len(desc_list) <= 1 and project['description']:
                    add_description_text(document, project['description'])
                else:
                    for desc in desc_list:
                        if desc:
                            add_bullet_point(document, desc)

    # ==================== SKILLS ====================
    if skills:
        add_section_heading(document, 'SKILLS')

        skill_names = [s['skill_name'] for s in skills]

        # Create a table for multi-column layout (3 columns)
        num_cols = 3
        num_skills = len(skill_names)
        rows_needed = (num_skills + num_cols - 1) // num_cols

        table = document.add_table(rows=rows_needed, cols=num_cols)
        table.autofit = True

        for i, skill in enumerate(skill_names):
            row_idx = i // num_cols
            col_idx = i % num_cols

            cell = table.cell(row_idx, col_idx)
            cell.text = ''
            para = cell.paragraphs[0]

            bullet_run = para.add_run('• ')
            bullet_run.font.name = 'Arial'
            bullet_run.font.size = Pt(10)

            skill_run = para.add_run(skill)
            skill_run.font.name = 'Arial'
            skill_run.font.size = Pt(10)
            skill_run.font.color.rgb = RGBColor(60, 60, 60)

        # Remove table borders
        for row in table.rows:
            for cell in row.cells:
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                tcBorders = OxmlElement('w:tcBorders')
                for border_name in ['top', 'left', 'bottom', 'right']:
                    border = OxmlElement(f'w:{border_name}')
                    border.set(qn('w:val'), 'nil')
                    tcBorders.append(border)
                tcPr.append(tcBorders)

    # Save to BytesIO
    file_stream = io.BytesIO()
    document.save(file_stream)
    file_stream.seek(0)

    return file_stream


def generate_tailored_resume(tailored_data: dict, job_title: str) -> io.BytesIO:
    """
    Generate a tailored DOCX resume using AI-rephrased content
    tailored_data contains: user, education, original_work_experiences, original_projects, original_skills, tailored
    """

    user = tailored_data['user']
    education = tailored_data['education']
    original_work = tailored_data['original_work_experiences']
    original_projects = tailored_data['original_projects']
    original_skills = tailored_data['original_skills']
    tailored = tailored_data['tailored']

    # Create document
    document = Document()

    # Set margins
    sections = document.sections
    for section in sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Set default font
    style = document.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(10)

    # ==================== HEADER - NAME ====================
    name_para = document.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_para.add_run(user['name'].upper())
    name_run.font.size = Pt(28)
    name_run.font.bold = True
    name_run.font.name = 'Arial'
    name_run.font.color.rgb = RGBColor(0, 0, 0)
    name_para.paragraph_format.space_after = Pt(4)
    name_para.paragraph_format.space_before = Pt(0)

    # ==================== PROFESSIONAL TITLE ====================
    # Use job title they're applying for as headline
    title_para = document.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_text = job_title if job_title else user.get('headline', '')
    title_run = title_para.add_run(title_text)
    title_run.font.size = Pt(14)
    title_run.font.name = 'Arial'
    title_run.font.color.rgb = RGBColor(60, 60, 60)
    title_para.paragraph_format.space_after = Pt(8)
    title_para.paragraph_format.space_before = Pt(0)

    # ==================== CONTACT INFO ROW ====================
    contact_para = document.add_paragraph()
    contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    contact_items = []

    if user.get('phone'):
        contact_items.append(('phone', user['phone']))
    if user.get('email'):
        contact_items.append(('email', user['email']))
    if user.get('location'):
        contact_items.append(('location', user['location']))

    for i, (icon_type, value) in enumerate(contact_items):
        if icon_type == 'phone':
            icon = '\u260E '
        elif icon_type == 'email':
            icon = '\u2709 '
        elif icon_type == 'location':
            icon = '\u2691 '
        else:
            icon = ''

        icon_run = contact_para.add_run(icon)
        icon_run.font.name = 'Arial'
        icon_run.font.size = Pt(10)
        icon_run.font.color.rgb = RGBColor(80, 80, 80)

        value_run = contact_para.add_run(value)
        value_run.font.name = 'Arial'
        value_run.font.size = Pt(10)
        value_run.font.color.rgb = RGBColor(80, 80, 80)

        if i < len(contact_items) - 1:
            spacer = contact_para.add_run('          ')
            spacer.font.size = Pt(10)

    contact_para.paragraph_format.space_after = Pt(12)

    # ==================== ABOUT ME (Tailored Summary) ====================
    if tailored.get('tailored_summary'):
        add_section_heading(document, 'ABOUT ME')
        add_description_text(document, tailored['tailored_summary'])

    # ==================== EDUCATION ====================
    if education:
        add_section_heading(document, 'EDUCATION')

        for edu in education:
            date_range = format_date_range(edu.get('start_date'), edu.get('end_date'))
            add_entry_header(document, edu['school'], date_range)

            degree_text = edu['degree']
            if edu.get('field_of_study'):
                degree_text += f" in {edu['field_of_study']}"
            add_entry_title(document, degree_text)

            if edu.get('description'):
                add_description_text(document, edu['description'])
            elif edu.get('gpa'):
                add_description_text(document, f"GPA: {edu['gpa']}")

    # ==================== WORK EXPERIENCE (Tailored) ====================
    tailored_work = tailored.get('tailored_work_experiences', [])
    if tailored_work or original_work:
        add_section_heading(document, 'WORK EXPERIENCE')

        tailored_work_map = {w.get('id'): w for w in tailored_work}

        for work in original_work:
            tailored_version = tailored_work_map.get(work['id'], {})

            date_range = format_date_range(work.get('start_date'), work.get('end_date'), work.get('is_current'))
            company = tailored_version.get('company', work['company'])
            title = tailored_version.get('title', work['title'])

            add_entry_header(document, company, date_range)
            add_entry_title(document, title)

            responsibilities = tailored_version.get('responsibilities', work.get('responsibilities', ''))

            if responsibilities:
                resp_list = [r.strip() for r in responsibilities.split('\n') if r.strip()]

                if len(resp_list) <= 1 and responsibilities:
                    add_description_text(document, responsibilities)
                else:
                    for resp in resp_list:
                        if resp:
                            add_bullet_point(document, resp)

    # ==================== PROJECTS (Tailored) ====================
    tailored_projects = tailored.get('tailored_projects', [])
    if tailored_projects or original_projects:
        add_section_heading(document, 'PROJECTS')

        tailored_proj_map = {p.get('id'): p for p in tailored_projects}

        for project in original_projects:
            tailored_version = tailored_proj_map.get(project['id'], {})

            date_range = ""
            if project.get('start_date'):
                date_range = format_date_range(project.get('start_date'), project.get('end_date'))

            title = tailored_version.get('title', project['title'])
            add_entry_header(document, title, date_range)

            if project.get('technologies'):
                tech_para = document.add_paragraph()
                tech_run = tech_para.add_run(f"Technologies: {project['technologies']}")
                tech_run.font.name = 'Arial'
                tech_run.font.size = Pt(9)
                tech_run.font.italic = True
                tech_run.font.color.rgb = RGBColor(100, 100, 100)
                tech_para.paragraph_format.space_after = Pt(4)

            description = tailored_version.get('description', project.get('description', ''))

            if description:
                desc_list = [d.strip() for d in description.split('\n') if d.strip()]

                if len(desc_list) <= 1 and description:
                    add_description_text(document, description)
                else:
                    for desc in desc_list:
                        if desc:
                            add_bullet_point(document, desc)

    # ==================== SKILLS (Tailored order) ====================
    tailored_skills = tailored.get('tailored_skills', [])
    if tailored_skills:
        add_section_heading(document, 'SKILLS')

        num_cols = 3
        num_skills = len(tailored_skills)
        rows_needed = (num_skills + num_cols - 1) // num_cols

        table = document.add_table(rows=rows_needed, cols=num_cols)
        table.autofit = True

        for i, skill in enumerate(tailored_skills):
            row_idx = i // num_cols
            col_idx = i % num_cols

            cell = table.cell(row_idx, col_idx)
            cell.text = ''
            para = cell.paragraphs[0]

            bullet_run = para.add_run('• ')
            bullet_run.font.name = 'Arial'
            bullet_run.font.size = Pt(10)

            skill_run = para.add_run(skill)
            skill_run.font.name = 'Arial'
            skill_run.font.size = Pt(10)
            skill_run.font.color.rgb = RGBColor(60, 60, 60)

        # Remove table borders
        for row in table.rows:
            for cell in row.cells:
                tc = cell._tc
                tcPr = tc.get_or_add_tcPr()
                tcBorders = OxmlElement('w:tcBorders')
                for border_name in ['top', 'left', 'bottom', 'right']:
                    border = OxmlElement(f'w:{border_name}')
                    border.set(qn('w:val'), 'nil')
                    tcBorders.append(border)
                tcPr.append(tcBorders)

    # Save to BytesIO
    file_stream = io.BytesIO()
    document.save(file_stream)
    file_stream.seek(0)

    return file_stream
