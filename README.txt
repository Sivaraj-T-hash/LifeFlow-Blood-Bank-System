==============================================================================
                  LIFEFLOW - BLOOD BANK MANAGEMENT SYSTEM
==============================================================================

[ PROJECT DESCRIPTION ]
LifeFlow is a comprehensive web-based platform designed to bridge the gap 
between blood donors, hospitals, and blood donation camps. It facilitates 
real-time communication, donor management, appointment scheduling, and blood 
stock tracking. The system features dedicated dashboards for Administrators, 
Hospitals, Camp Hosts, and Donors.

------------------------------------------------------------------------------
[ KEY FEATURES ]
------------------------------------------------------------------------------

1. DONOR (USER) MODULE
   - Secure Registration & Login: Users can create accounts and log in.
   - Dashboard & Profile: View personal stats, edit details, and update password.
   - Book Appointments: 
     * Schedule time slots at registered hospitals.
     * Register for upcoming blood donation camps.
   - Log Past Donations: Manually log previous donations. These requests are sent
     to the respective hospital for verification before being added to the history.
   - Eligibility Check: Automated system prevents booking if the last donation 
     (verified or self-logged) was within 90 days.
   - Certificates: Auto-generated PDF certificates available for download after
     a donation is verified.
   - Donation History: View logs of all past donations with status (Pending, 
     Verified, Rejected).

2. HOSPITAL MODULE
   - Dashboard: Real-time overview of upcoming appointments and verification queues.
   - Verification System:
     * Approve/Reject manual "Past Donation" logs from users.
     * Verify scheduled appointments upon completion.
   - Export Data:
     * Donation History: Filter by date/blood group; download as CSV or PDF.
     * Appointment Logs: Filter by status/date; download as CSV or PDF.
   - Real-Time Stock: Approved donations automatically update the public stock view.

3. CAMP HOST MODULE
   - Camp Management: Schedule new camps (Date, Time, Location, Capacity).
   - Donor Management: View list of registered donors for specific camps.
   - Export Data: Download donor lists for camps (PDF/CSV).
   - Photo Upload: Upload photos from completed camps to the public gallery.

4. ADMIN MODULE (SUPER ADMIN)
   - User Management: Add, Edit, or Delete Donors, Hospitals, and Camp Hosts.
   - Gallery Management: View all home page photos and delete specific images.
   - Advanced Reporting:
     * Blood Donation Logs (with Donor Names).
     * Hospital Performance (Total units collected).
     * Camp History Logs.
   - Export System: All reports available in CSV and Landscape PDF formats.

5. PUBLIC FEATURES
   - Interactive Map: 
     * Hospitals (Red Markers) showing live blood stock.
     * Camps (Orange Markers) showing registration counts.
   - Photo Gallery: Dynamic carousel of recent camp photos.
   - Live Statistics: Total Donors, Lives Saved, and Blood Units Collected.

------------------------------------------------------------------------------
[ TECHNOLOGY STACK ]
------------------------------------------------------------------------------
- Backend: Python (Flask)
- Database: SQLite (Relational)
- Frontend: HTML5, CSS3 (Bootstrap), JavaScript
- Mapping: Leaflet.js (OpenStreetMap)
- PDF Generation: FPDF
- Security: Werkzeug Security (Password Hashing)

------------------------------------------------------------------------------
[ INSTALLATION & SETUP ]
------------------------------------------------------------------------------
1. Install Python (if not already installed).
2. Install required packages:
   $ pip install flask fpdf
3. Run the application:
   $ python app.py
4. Open your browser and navigate to:
   http://127.0.0.1:5000

------------------------------------------------------------------------------
[ DEFAULT CREDENTIALS FOR TESTING ]
------------------------------------------------------------------------------
* Admin Login:
  Email: admin@bloodbank.com
  Pass:  admin123

* Hospital/Host/User: 
  You can register new accounts via the registration pages or add them 
  through the Admin Dashboard.

==============================================================================