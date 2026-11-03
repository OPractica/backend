from app.models.database import Booking


def booking_confirmed_html(booking: Booking, seat_label: str) -> tuple[str, str]:
    # Returns (subject, html) for booking confirmation in EN and RO.
    subject = f"Booking confirmed: {seat_label}"
    html = f"""\
<h2>Booking Confirmed</h2>
<p><i>Your desk has been successfully booked.</i></p>
<ul>
    <li><b>Desk:</b> {seat_label}</li>
    <li><b>Date:</b> {booking.starts_at:%d.%m.%Y}</li>
    <li><b>Time:</b> {booking.starts_at:%H:%M} - {booking.ends_at:%H:%M}</li>
</ul>
<p>This is an automated email, please do not reply.</p>

<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;" />

<h2>Rezervare confirmată</h2>
<p><i>Locul dvs. a fost rezervat cu succes.</i></p>
<ul>
  <li><b>Loc:</b> {seat_label}</li>
  <li><b>Data:</b> {booking.starts_at:%d.%m.%Y}</li>
  <li><b>Ora:</b> {booking.starts_at:%H:%M} — {booking.ends_at:%H:%M}</li>
</ul>
<p>Acesta este un mesaj automat, vă rugăm să nu răspundeți.</p>
"""
    return subject, html


def booking_cancelled_html(booking: Booking, seat_label: str) -> tuple[str, str]:
    # Returns (subject, html) for booking cancellation in EN and RO.
    subject = f"Booking cancelled: {seat_label}"
    html = f"""\
<h2>Booking Cancelled</h2>
<p><i>Your booking has been cancelled.</i></p>
<ul>
  <li><b>Desk:</b> {seat_label}</li>
  <li><b>Date:</b> {booking.starts_at:%d.%m.%Y}</li>
  <li><b>Time:</b> {booking.starts_at:%H:%M} — {booking.ends_at:%H:%M}</li>
</ul>
<p>This is an automated email, please do not reply.</p>
<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 20px 0;" />
<h2>Rezervare anulată</h2>
<p><i>Rezervarea dvs. a fost anulată.</i></p>
<ul>
  <li><b>Loc:</b> {seat_label}</li>
  <li><b>Data:</b> {booking.starts_at:%d.%m.%Y}</li>
  <li><b>Ora:</b> {booking.starts_at:%H:%M} — {booking.ends_at:%H:%M}</li>
</ul>
<p>Acesta este un mesaj automat, vă rugăm să nu răspundeți.</p>
"""
    return subject, html
