from fpdf import FPDF

class PDFReport(FPDF):
    def header(self):
        self.set_fill_color(220, 53, 69) # Danger Red
        self.rect(0, 0, 210, 20, 'F')
        self.set_font('Arial', 'B', 18)
        self.set_text_color(255, 255, 255)
        self.set_y(5)
        self.cell(0, 10, 'LIFEFLOW: ADVANCED DBMS ARCHITECTURE & FEATURES', 0, 1, 'C')
        self.set_y(25)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'LifeFlow Project Documentation - Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.set_text_color(220, 53, 69)
        self.cell(0, 10, title, 0, 1, 'L')
        self.set_draw_color(220, 53, 69)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def bullet_point(self, title, description):
        # 1. Print Bullet and Title
        self.set_font('Arial', 'B', 11)
        self.set_text_color(33, 37, 41)
        self.cell(7, 6, chr(149), 0, 0) # Bullet character
        self.cell(0, 6, title + ":", 0, 1) # Title takes full width, then line breaks
        
        # 2. Print Description (Nicely Indented)
        self.set_font('Arial', '', 11)
        original_l_margin = self.l_margin
        self.set_left_margin(17) # Indent the text by 17mm
        self.multi_cell(0, 6, description)
        self.set_left_margin(original_l_margin) # Reset margin for next item
        self.ln(4)

# Initialize PDF
pdf = PDFReport()
pdf.add_page()

# --- SECTION 1: ADVANCED DBMS ENGINEERING ---
pdf.chapter_title("1. Core DBMS Engineering & Optimization")
pdf.bullet_point("ACID-Compliant Transactions", "Utilized 'BEGIN EXCLUSIVE TRANSACTION' during appointment bookings to enforce Isolation and Atomicity, preventing race conditions and double-booking if multiple users access the system simultaneously.")
pdf.bullet_point("SQL Database Triggers", "Implemented 'AFTER UPDATE' triggers on the database level. Automatically captures status changes (Approvals/Rejections) and writes them to a hidden 'security_audit_log' table, ensuring tamper-proof data auditing.")
pdf.bullet_point("B-Tree Indexing", "Engineered B-Tree Indexes on critical columns (blood_group, status) to optimize query execution plans, reducing Full Table Scans to O(log N) complexity for emergency scaling.")
pdf.bullet_point("Window Functions (AI Analytics)", "Utilized SQL Window Functions (AVG() OVER (PARTITION BY)) to calculate global moving averages inside the database engine. This creates a Predictive AI Shortage Warning system without relying on Python loops.")
pdf.bullet_point("Spatial Queries (Haversine Formula)", "Injected custom Python scalar functions directly into the SQLite engine to perform spherical trigonometry (Haversine Formula) directly in SQL, enabling radius-based geographic searches for the SOS feature.")
pdf.ln(2)

# --- SECTION 2: EXPORTING & REPORTING ---
pdf.chapter_title("2. Dynamic Reporting & Certification")
pdf.bullet_point("Automated PDF Certificates", "Dynamically generates localized PDF 'Certificates of Donation' using FPDF, instantly rewarding donors upon hospital verification.")
pdf.bullet_point("Hospital Analytics Export", "Hospitals can apply multi-parameter filters (Date, Blood Group, Status) and export customized CSV or PDF reports of their operational history and verified appointments.")
pdf.bullet_point("Admin Global Reports", "Super Admins can generate and download system-wide CSV/PDF reports encompassing Total Donations, Hospital Performance rankings, User Directories, and Camp Logs.")
pdf.bullet_point("Camp Organizer Exports", "Camp Hosts can automatically export PDF/CSV manifests of registered donors for event-day management.")
pdf.ln(2)

# --- SECTION 3: SYSTEM FEATURES & WORKFLOWS ---
pdf.chapter_title("3. Platform Workflows & UI Integration")
pdf.bullet_point("Public & Hospital SOS Radar", "Both public users and hospital staff can trigger an 'SOS Emergency Radar' that utilizes HTML5 Geolocation and Spatial SQL to instantly locate and list the contact details of the nearest eligible donors.")
pdf.bullet_point("Automated SMTP Emailing", "Integrated Python's smtplib with Google App Passwords to dispatch highly professional, automated email confirmations to users the millisecond a database transaction successfully commits.")
pdf.bullet_point("Gamified Leaderboard (Hall of Fame)", "A custom SQL aggregate query calculates top donors by volume, rendering a CSS-animated, dynamic 'Podium' on the homepage to incentivize donations.")
pdf.bullet_point("Live Inventory Mapping", "Integrated Leaflet.js mapping API. The map dynamically aggregates BOTH internal verified donations and manual external inventory added securely by hospitals, showing real-time blood stock across the state.")
pdf.bullet_point("Admin Override System", "Super Admins retain full CRUD capabilities to modify users, delete hospitals, add manual legacy donation units directly to a user's total, and monitor the automated Trigger Audit Log.")

# Output the PDF
output_filename = "LifeFlow_Project_Features_Report.pdf"
pdf.output(output_filename)
print(f"✅ Success! {output_filename} has been generated without overlapping text.")