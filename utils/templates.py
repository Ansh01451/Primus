from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
from config import settings


def verify_otp_template(name: str, otp: str) -> str:
    year = datetime.now().year
    return f"""
          <div style="background-color: #e7f0f8; font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 0; border: 2px solid #f0f0f0; border-radius: 30px; box-shadow: 0 10px 15px -5px rgba(0, 0, 0, 0.1); overflow: hidden;">
          <!-- Header -->
          <div style="background-color: #2E5BFF; border-bottom: 4px solid white; box-shadow: 0 5px 10px -5px rgba(0, 0, 0, 0.1); height: 80px; width: 100%; display: flex; justify-content: center; align-items: center;">
              <h2 style="color: white; margin: auto; font-size: 20px; font-weight: bold; text-align: center;">Password Reset Request</h2>
          </div>

          <!-- Content -->
          <div style="padding: 20px; background-color: #ffffff;">
              <div style="text-align: center; margin-bottom: 20px;">
                  <span style="font-size: 32px; font-weight: bold; color: #2E5BFF; text-decoration: none; display: inline-block;">PRIMUS</span>
              </div>

              <p style="font-size: 14px; color: #333; margin: 0; margin-top: 10px;">
                  Hello <strong>{name}</strong>,
              </p>

              <p style="font-size: 14px; color: #333; margin: 10px 0;">
                  We received a request to reset your password. Use the One-Time Password (OTP) below to reset your password:
              </p>

              <div style="text-align: center; margin: 20px 0;">
                  <h2 style="border: 2px dashed #2E5BFF; padding: 10px 20px; color: #2E5BFF; background-color: #f9f9f9; display: inline-block; border-radius: 5px; font-family: monospace;">{otp}</h2>
              </div>

              <p style="font-size: 14px; color: #333; margin: 10px 0;">
                  This OTP is valid for the next <strong>10 minutes</strong>. If you did not request a password reset, you can safely ignore this email. Your account is secure.
              </p>

              <p style="font-size: 14px; color: #333; margin: 10px 0;">
                  For your security, do not share this OTP with anyone. If you face any issues, feel free to reach out to us.
              </p>
          </div>

          <!-- Footer -->
          <div style="background-color: #f9f9f9; padding: 15px; text-align: center; border-top: 1px solid #ddd; border-radius: 0 0 30px 30px;">
              <p style="font-size: 12px; color: #777; margin: 0;">
                  Please do not reply to this email. If you need further support, visit our 
                  <a href="{
                    settings.support_url
                  }" target="_blank" style="color: #2E5BFF; text-decoration: none;">Support Page</a>.
              </p>
              <p style="font-size: 12px; color: #777; margin: 10px 0;">&copy; {datetime.now().year} Primus. All rights reserved.</p>
          </div>
        </div>"""


def client_details_template(client_id: str, name: str, email: str, project_id: str, password: str) -> str:
    """
    HTML email to send a newly registered client their credentials.
    """
    year = datetime.now().year
    return f"""
    <div style="background-color: #e7f0f8; font-family: Arial, sans-serif;
                max-width: 600px; margin: 0 auto; padding: 0;
                border: 2px solid #f0f0f0; border-radius: 30px;
                box-shadow: 0 10px 15px -5px rgba(0, 0, 0, 0.1); overflow: hidden;">
      <!-- Header -->
      <div style="background-color: #2E5BFF; border-bottom: 4px solid white;
                  height: 80px; display: flex; justify-content: center;
                  align-items: center;">
        <h2 style="color: white; font-size: 20px; font-weight: bold;">
          Your Account is Ready!
        </h2>
      </div>

      <!-- Content -->
      <div style="padding: 20px; background-color: #ffffff;">
        <p style="font-size:14px; color:#333;">
          Hello <strong>{name}</strong>,
        </p>
        <p style="font-size:14px; color:#333; margin-top:10px;">
          Your client account has been created successfully. Below are your login credentials:
        </p>

        <table style="width:100%; margin:20px 0; border-collapse: collapse;">
          <tr>
            <td style="padding:8px; font-weight:bold; width:30%;">Client ID:</td>
            <td style="padding:8px;">{client_id}</td>
          </tr>
          <tr>
            <td style="padding:8px; font-weight:bold;">Email:</td>
            <td style="padding:8px;">{email}</td>
          </tr>
          <tr>
            <td style="padding:8px; font-weight:bold;">Password:</td>
            <td style="padding:8px;">{password}</td>
          </tr>
          <tr>
            <td style="padding:8px; font-weight:bold;">Project ID:</td>
            <td style="padding:8px;">{project_id}</td>
          </tr>
        </table>

        <p style="font-size:14px; color:#333;">
          For security, please log in and change your password immediately.
        </p>
      </div>

      <!-- Footer -->
      <div style="background-color: #f9f9f9; padding: 15px;
                  text-align: center; border-top:1px solid #ddd;">
        <p style="font-size:12px; color:#777; margin:0;">
          Need help? Visit our
          <a href="{settings.support_url}" style="color:#2E5BFF; text-decoration:none;">
            Support Page
          </a>.
        </p>
        <p style="font-size: 12px; color: #777; margin: 10px 0;">&copy; {datetime.now().year} Primus. All rights reserved.</p>
      </div>
    </div>
    """


def client_escalation_notification_template(
    tracking_id: str,
    client_id: str,
    client_name: str,
    client_email: str,
    project_id: str,
    project_manager: str,
    project_manager_email: str,
    project_name: str,
    escalation_type: str,
    urgency: str,
    subject: str,
    description: str,
    date_of_escalation: datetime,
    attachments: Optional[List[Dict[str, str]]] = None
) -> str:
    # Format dates
    created_str = date_of_escalation.strftime("%Y-%m-%d %H:%M UTC")

    html = f"""
    <div style="background:#e7f0f8;font-family:Arial,sans-serif;
                max-width:600px;margin:0 auto;padding:0;
                border:2px solid #f0f0f0;border-radius:8px;
                box-shadow:0 2px 6px rgba(0,0,0,0.1);">
      <!-- Header -->
      <div style="background:#2E5BFF;color:#fff;padding:15px;
                  text-align:center;font-size:18px;font-weight:bold;">
        New Request – {project_name}
      </div>

      <div style="background:#fff;padding:20px;">
        <!-- Client Details -->
        <h3>Client Details</h3>
        <ul style="list-style:none;padding:0;margin:0 0 15px 0;">
          <li><strong>Name:</strong> {client_name}</li>
          <li><strong>ID:</strong> {client_id}</li>
          <li><strong>Email:</strong> <a href="mailto:{client_email}">{client_email}</a></li>
        </ul>

        <!-- Project Details -->
        <h3>Requested To:</h3>
        <ul style="list-style:none;padding:0;margin:0 0 15px 0;">
          <li><strong>Name:</strong> {project_name}</li>
          <li><strong>Designation:</strong> Manager </li>
          <li><strong>Email:</strong>  <a href="mailto:{project_manager_email}">{project_manager_email}</a></li>
        </ul>

        <!-- Escalation Info -->
        <h3>Request Information</h3>
        <table style="width:100%;border-collapse:collapse;margin-bottom:15px;">
          <tr>
            <td style="padding:8px;font-weight:bold;">Tracking ID:</td>
            <td style="padding:8px;">{tracking_id}</td>
          </tr>
          <tr>
            <td style="padding:8px;font-weight:bold;">Raised On:</td>
            <td style="padding:8px;">{created_str}</td>
          </tr>
          <tr>
            <td style="padding:8px;font-weight:bold;">Category:</td>
            <td style="padding:8px;">{escalation_type.capitalize()}</td>
          </tr>
          <tr>
            <td style="padding:8px;font-weight:bold;">Priority:</td>
            <td style="padding:8px;">{urgency.capitalize()}</td>
          </tr>
        </table>
        
        <!-- Subject -->
        <p style="margin:0 0 15px;"><strong>Subject:</strong></p>
        <p style="background:#f9f9f9;padding:15px;border-radius:5px;margin:0 0 15px;">{subject}</p>

        <!-- Description -->
        <p style="margin:0 0 15px;"><strong>Description:</strong></p>
        <p style="background:#f9f9f9;padding:15px;border-radius:5px;margin:0 0 15px;">{description}</p>
    """

    # Attachments
    if attachments:
        html += """
        <div style="background:#fff;padding:20px;">
          <h3>Attachments</h3>
          <ul style="margin:0;padding-left:20px;">"""
        for att in attachments:
            html += f"""
            <li><a href="{att['url']}" target="_blank">{att['filename']}</a></li>"""
        html += """
          </ul>
        </div>"""

    # Footer
    html += f"""
      </div>
      <div style="background:#f9f9f9;padding:15px;
                  text-align:center;border-top:1px solid #ddd;">
        <p style="font-size:12px;color:#777;margin:0;">
          Questions? Visit our
          <a href="{settings.support_url}" style="color:#2E5BFF;text-decoration:none;">
            Support Page
          </a>.
        </p>
        <p style="font-size:12px;color:#777;margin:10px 0 0 0;">
          &copy; {datetime.now().year} Primus. All rights reserved.
        </p>
      </div>
    </div>
    """
    return html


def render_stars(value: Optional[int]) -> str:
    if value is None:
        return "—"
    full = "★" * value
    empty = "☆" * (5 - value)
    return f"<span style='color:#f5a623;font-size:16px;'>{full}{empty}</span>"


def client_feedback_notification_template(
    feedback_id: str,
    client_email: str,
    project_no: str,
    project_name: Optional[str],
    project_manager_email: str,
    category: str,
    team_member_id: Optional[str],
    milestone_name: Optional[str],
    communication_quality: Optional[int],
    team_collaboration: Optional[int],
    solution_quality: Optional[int],
    overall_satisfaction: Optional[int],
    comments: Optional[str],
    created_at: datetime,
    attachments: Optional[List[Dict[str, str]]] = None
) -> str:
    created_str = created_at.strftime("%Y-%m-%d %H:%M UTC")

    html = f"""
    <div style="background:#f7fbff;font-family:Arial,sans-serif;
                max-width:700px;margin:0 auto;padding:0;border-radius:8px;
                border:1px solid #eee;">
      <div style="background:#0b63ff;color:#fff;padding:14px 20px;border-top-left-radius:8px;border-top-right-radius:8px;">
        <strong>New Feedback Received</strong>
      </div>

      <div style="padding:18px;background:#ffffff;">
        <h3 style="margin:0 0 12px 0;">Project: {project_name or project_no}</h3>

        <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">
          <tr>
            <td style="padding:6px;font-weight:600;width:160px;">Project No:</td>
            <td style="padding:6px;">{project_no}</td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Client Email:</td>
            <td style="padding:6px;"><a href='mailto:{client_email}'>{client_email}</a></td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Category:</td>
            <td style="padding:6px;">{category}</td>
          </tr>
      """
      # ✅ Conditionally show milestone row
    if milestone_name:
        html += f"""
          <tr>
            <td style="padding:6px;font-weight:600;">Milestone Name:</td>
            <td style="padding:6px;">{milestone_name}</td>
          </tr>
        """
    html += f"""
          <tr>
            <td style="padding:6px;font-weight:600;">Team Member:</td>
            <td style="padding:6px;">{team_member_id or '—'}</td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Communication Quality:</td>
            <td style="padding:6px;">{render_stars(communication_quality)}</td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Team Collaboration:</td>
            <td style="padding:6px;">{render_stars(team_collaboration)}</td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Solution Quality:</td>
            <td style="padding:6px;">{render_stars(solution_quality)}</td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Overall Satisfaction:</td>
            <td style="padding:6px;">{render_stars(overall_satisfaction)}</td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Received At:</td>
            <td style="padding:6px;">{created_str}</td>
          </tr>
        </table>

        <div style="margin:12px 0;">
          <p style="margin:0 0 6px 0;font-weight:600;">Comments:</p>
          <div style="background:#f6f8fb;padding:12px;border-radius:6px;color:#222;">
            {comments or "<i>No comments provided</i>"}
          </div>
        </div>

        <div style="margin-top:16px;">
            <p style="margin:0;font-size:14px;">
              <strong>Project Manager:</strong> 
              &nbsp;<a href="mailto:{project_manager_email}">{project_manager_email}</a>
            </p>
        </div>
      </div>
    """

    # CHANGED: Group attachments by category and render each category separately
    if attachments:
        # Group attachments by 'category' key
        grouped = defaultdict(list)
        for att in attachments:
            cat = att.get("category") or "uncategorized"  # CHANGED: expect 'category' in each attachment dict
            grouped[cat].append(att)

        # Friendly labels for known attachment categories
        CATEGORY_LABELS = {
            "experience_letter": "Experience Letter",
            "appreciation_letter": "Appreciation Letter",
            "completion_certificate": "Completion Certificate",
            "uncategorized": "Attachments"
        }  # CHANGED: mapping to display nicer headings

        html += """
        <div style="background:#fff;padding:20px;">
          <h3>Attachments</h3>
        """

        # Render each category section in a predictable order (experience -> appreciation -> completion -> others)
        preferred_order = ["experience_letter", "appreciation_letter", "completion_certificate"]
        rendered_categories = set()

        for key in preferred_order:
            items = grouped.get(key)
            if items:
                label = CATEGORY_LABELS.get(key, key.replace("_", " ").title())
                html += f"""<div style="margin-top:10px;"><h4 style="margin:6px 0;">{label} ({len(items)})</h4>
                            <ul style="margin:0;padding-left:20px;">"""
                for att in items:
                    filename = att.get("filename", "file")
                    url = att.get("url", "#")
                    html += f'<li><a href="{url}" target="_blank">{filename}</a></li>'
                html += "</ul></div>"
                rendered_categories.add(key)

        # Render any other categories not in preferred order
        for cat, items in grouped.items():
            if cat in rendered_categories:
                continue
            label = CATEGORY_LABELS.get(cat, cat.replace("_", " ").title())
            html += f"""<div style="margin-top:10px;"><h4 style="margin:6px 0;">{label} ({len(items)})</h4>
                        <ul style="margin:0;padding-left:20px;">"""
            for att in items:
                filename = att.get("filename", "file")
                url = att.get("url", "#")
                html += f'<li><a href="{url}" target="_blank">{filename}</a></li>'
            html += "</ul></div>"

        html += """
        </div>"""

    # Footer
    html += f"""
      </div>
      <div style="background:#f9f9f9;padding:15px;
                  text-align:center;border-top:1px solid #ddd;">
        <p style="font-size:12px;color:#777;margin:0;">
          Questions? Visit our
          <a href="{settings.support_url}" style="color:#2E5BFF;text-decoration:none;">
            Support Page
          </a>.
        </p>
        <p style="font-size:12px;color:#777;margin:10px 0 0 0;">
          &copy; {datetime.now().year} Primus. All rights reserved.
        </p>
      </div>
    </div>
    """
    
    return html


def vendor_feedback_notification_template( 
    feedback_id: str,
    vendor_email: str,
    category: str,
    team_member_id: Optional[str],
    communication_quality: Optional[int],
    team_collaboration: Optional[int],
    overall_satisfaction: Optional[int],
    comments: Optional[str],
    created_at: datetime,
    attachments: Optional[List[Dict[str, str]]] = None
) -> str:
    created_str = created_at.strftime("%Y-%m-%d %H:%M UTC")

    html = f"""
    <div style="background:#f7fbff;font-family:Arial,sans-serif;
                max-width:700px;margin:0 auto;padding:0;border-radius:8px;
                border:1px solid #eee;">
      <div style="background:#0b63ff;color:#fff;padding:14px 20px;border-top-left-radius:8px;border-top-right-radius:8px;">
        <strong>New Vendor Feedback Received</strong>
      </div>

      <div style="padding:18px;background:#ffffff;">
        <h3 style="margin:0 0 12px 0;">Feedback ID: {feedback_id}</h3>

        <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">
          <tr>
            <td style="padding:6px;font-weight:600;width:160px;">Vendor Email:</td>
            <td style="padding:6px;"><a href='mailto:{vendor_email}'>{vendor_email}</a></td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Category:</td>
            <td style="padding:6px;">{category}</td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Communication Quality:</td>
            <td style="padding:6px;">{render_stars(communication_quality)}</td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Team Collaboration:</td>
            <td style="padding:6px;">{render_stars(team_collaboration)}</td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Overall Satisfaction:</td>
            <td style="padding:6px;">{render_stars(overall_satisfaction)}</td>
          </tr>
          <tr>
            <td style="padding:6px;font-weight:600;">Received At:</td>
            <td style="padding:6px;">{created_str}</td>
          </tr>
        </table>

        <div style="margin:12px 0;">
          <p style="margin:0 0 6px 0;font-weight:600;">Comments:</p>
          <div style="background:#f6f8fb;padding:12px;border-radius:6px;color:#222;">
            {comments or "<i>No comments provided</i>"}
          </div>
        </div>
      </div>
    """

    # Attachments
    if attachments:
        html += """
        <div style="background:#fff;padding:20px;">
          <h3>Attachments</h3>
          <ul style="margin:0;padding-left:20px;">"""
        for att in attachments:
            html += f"""
            <li><a href="{att['url']}" target="_blank">{att['filename']}</a></li>"""
        html += """
          </ul>
        </div>"""

    # Footer
    html += f"""
      <div style="background:#f9f9f9;padding:15px;
                  text-align:center;border-top:1px solid #ddd;">
        <p style="font-size:12px;color:#777;margin:0;">
          Questions? Visit our
          <a href="{settings.support_url}" style="color:#2E5BFF;text-decoration:none;">
            Support Page
          </a>.
        </p>
        <p style="font-size:12px;color:#777;margin:10px 0 0 0;">
          &copy; {datetime.now().year} Primus. All rights reserved.
        </p>
      </div>
    </div>
    """
    
    return html


def vendor_escalation_notification_template( 
    tracking_id: str,
    vendor_id: str,
    vendor_name: str,
    vendor_email: str,
    escalation_type: str,
    urgency: str,
    subject: str,
    description: str,
    date_of_escalation: datetime,
    attachments: Optional[List[Dict[str, str]]] = None
) -> str:
    # Format date
    created_str = date_of_escalation.strftime("%Y-%m-%d %H:%M UTC")

    html = f"""
    <div style="background:#e7f0f8;font-family:Arial,sans-serif;
                max-width:600px;margin:0 auto;padding:0;
                border:2px solid #f0f0f0;border-radius:8px;
                box-shadow:0 2px 6px rgba(0,0,0,0.1);">
      <!-- Header -->
      <div style="background:#2E5BFF;color:#fff;padding:15px;
                  text-align:center;font-size:18px;font-weight:bold;">
        New Vendor Escalation Received
      </div>

      <div style="background:#fff;padding:20px;">
        <!-- Vendor Details -->
        <h3>Vendor Details</h3>
        <ul style="list-style:none;padding:0;margin:0 0 15px 0;">
          <li><strong>Name:</strong> {vendor_name or "—"}</li>
          <li><strong>ID:</strong> {vendor_id}</li>
          <li><strong>Email:</strong> <a href="mailto:{vendor_email}">{vendor_email}</a></li>
        </ul>

        <!-- Escalation Info -->
        <h3>Escalation Information</h3>
        <table style="width:100%;border-collapse:collapse;margin-bottom:15px;">
          <tr>
            <td style="padding:8px;font-weight:bold;">Tracking ID:</td>
            <td style="padding:8px;">{tracking_id}</td>
          </tr>
          <tr>
            <td style="padding:8px;font-weight:bold;">Raised On:</td>
            <td style="padding:8px;">{created_str}</td>
          </tr>
          <tr>
            <td style="padding:8px;font-weight:bold;">Category:</td>
            <td style="padding:8px;">{escalation_type.replace('_', ' ').title()}</td>
          </tr>
          <tr>
            <td style="padding:8px;font-weight:bold;">Urgency:</td>
            <td style="padding:8px;">{urgency.capitalize()}</td>
          </tr>
        </table>

        <!-- Subject -->
        <p style="margin:0 0 15px;"><strong>Subject:</strong></p>
        <p style="background:#f9f9f9;padding:15px;border-radius:5px;margin:0 0 15px;">{subject}</p>

        <!-- Description -->
        <p style="margin:0 0 15px;"><strong>Description:</strong></p>
        <p style="background:#f9f9f9;padding:15px;border-radius:5px;margin:0 0 15px;">{description}</p>
    """

    # Attachments
    if attachments:
        html += """
        <div style="background:#fff;padding:20px;">
          <h3>Attachments</h3>
          <ul style="margin:0;padding-left:20px;">"""
        for att in attachments:
            html += f"""
            <li><a href="{att['url']}" target="_blank">{att['filename']}</a></li>"""
        html += """
          </ul>
        </div>"""

    # Footer
    html += f"""
      </div>
      <div style="background:#f9f9f9;padding:15px;
                  text-align:center;border-top:1px solid #ddd;">
        <p style="font-size:12px;color:#777;margin:0;">
          Questions? Visit our
          <a href="{settings.support_url}" style="color:#2E5BFF;text-decoration:none;">
            Support Page
          </a>.
        </p>
        <p style="font-size:12px;color:#777;margin:10px 0 0 0;">
          &copy; {datetime.now().year} Primus. All rights reserved.
        </p>
      </div>
    </div>
    """
    return html


def onboarded_user_template(
    name: str,
    email: str,
    role: str,
    dynamics_id: str,
    password: str,
) -> str:
    """
    Welcome email sent to a user who was just onboarded by an admin.
    """
    role_label = role.title()
    year = datetime.now().year
    return f"""
    <div style="background-color:#e7f0f8;font-family:Arial,sans-serif;
                max-width:600px;margin:0 auto;padding:0;
                border:2px solid #f0f0f0;border-radius:30px;
                box-shadow:0 10px 15px -5px rgba(0,0,0,0.1);overflow:hidden;">
      <!-- Header -->
      <div style="background-color:#2E5BFF;border-bottom:4px solid white;
                  height:80px;display:flex;justify-content:center;align-items:center;">
        <h2 style="color:white;font-size:20px;font-weight:bold;margin:0;">
          Welcome to the Portal!
        </h2>
      </div>

      <!-- Content -->
      <div style="padding:20px;background-color:#ffffff;">
        <p style="font-size:14px;color:#333;margin:0;">
          Hello <strong>{name}</strong>,
        </p>
        <p style="font-size:14px;color:#333;margin:12px 0;">
          Your <strong>{role_label}</strong> account has been created by the Primus admin team.
          Below are your login credentials:
        </p>

        <table style="width:100%;margin:20px 0;border-collapse:collapse;">
          <tr>
            <td style="padding:8px;font-weight:bold;width:35%;color:#555;">Dynamics ID:</td>
            <td style="padding:8px;">{dynamics_id}</td>
          </tr>
          <tr style="background:#f9f9f9;">
            <td style="padding:8px;font-weight:bold;color:#555;">Login Email:</td>
            <td style="padding:8px;">{email}</td>
          </tr>
          <tr>
            <td style="padding:8px;font-weight:bold;color:#555;">Temporary Password:</td>
            <td style="padding:8px;font-family:monospace;letter-spacing:1px;">{password}</td>
          </tr>
          <tr style="background:#f9f9f9;">
            <td style="padding:8px;font-weight:bold;color:#555;">Role:</td>
            <td style="padding:8px;">{role_label}</td>
          </tr>
        </table>

        <p style="font-size:14px;color:#c0392b;margin:10px 0;">
          &#128274; For security, please log in and <strong>change your password immediately</strong>.
        </p>
      </div>

      <!-- Footer -->
      <div style="background-color:#f9f9f9;padding:15px;
                  text-align:center;border-top:1px solid #ddd;">
        <p style="font-size:12px;color:#777;margin:0;">
          Need help? Visit our
          <a href="{settings.support_url}" style="color:#2E5BFF;text-decoration:none;">
            Support Page
          </a>.
        </p>
        <p style="font-size:12px;color:#777;margin:10px 0;">&copy; {year} Primus. All rights reserved.</p>
      </div>
    </div>
    """


def admin_reset_password_template(name: str, email: str, new_password: str) -> str:
    """
    Email sent to a user when an admin resets their portal password.
    """
    from datetime import datetime
    year = datetime.now().year
    return f"""
    <div style="background-color:#e7f0f8;font-family:Arial,sans-serif;
                max-width:600px;margin:0 auto;padding:0;
                border:2px solid #f0f0f0;border-radius:30px;
                box-shadow:0 10px 15px -5px rgba(0,0,0,0.1);overflow:hidden;">

      <!-- Header -->
      <div style="background-color:#2E5BFF;border-bottom:4px solid white;
                  height:80px;display:flex;justify-content:center;align-items:center;">
        <h2 style="color:white;font-size:20px;font-weight:bold;margin:0;">
          Your Password Has Been Reset
        </h2>
      </div>

      <!-- Content -->
      <div style="padding:24px;background-color:#ffffff;">
        <p style="font-size:14px;color:#333;margin:0;">
          Hello <strong>{name}</strong>,
        </p>
        <p style="font-size:14px;color:#333;margin:12px 0;">
          An administrator has reset your Primus portal password.
          Your new temporary credentials are below:
        </p>

        <table style="width:100%;margin:20px 0;border-collapse:collapse;">
          <tr style="background:#f9f9f9;">
            <td style="padding:10px;font-weight:bold;width:35%;color:#555;">Login Email:</td>
            <td style="padding:10px;">{email}</td>
          </tr>
          <tr>
            <td style="padding:10px;font-weight:bold;color:#555;">New Password:</td>
            <td style="padding:10px;font-family:monospace;letter-spacing:2px;
                       font-size:16px;color:#2E5BFF;font-weight:bold;">{new_password}</td>
          </tr>
        </table>

        <div style="background:#fff3cd;border-left:4px solid #ffc107;
                    padding:12px 16px;border-radius:6px;margin:16px 0;">
          <p style="font-size:13px;color:#856404;margin:0;">
            ⚠️ <strong>Important:</strong> Please log in and change this password immediately.
            Do not share it with anyone.
          </p>
        </div>

        <p style="font-size:13px;color:#666;margin:16px 0 0 0;">
          If you did not expect this change, please contact your administrator immediately.
        </p>
      </div>

      <!-- Footer -->
      <div style="background-color:#f9f9f9;padding:15px;
                  text-align:center;border-top:1px solid #ddd;">
        <p style="font-size:12px;color:#777;margin:0;">&copy; {year} Primus. All rights reserved.</p>
      </div>
    </div>
    """
