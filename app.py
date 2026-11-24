import os
import secrets
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template_string, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-apex-secret")

@app.after_request
def close_html_document(response):
    if response.mimetype == "text/html":
        response.set_data(
            response.get_data(as_text=True) + "</body></html>"
        )
    return response


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "dbname=apexinvest_new"
)

def db():
    con = psycopg2.connect(DATABASE_URL)
    cur = con.cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS apexinvest")
    cur.execute("SET search_path TO apexinvest")
    cur.close()
    return con

def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            fullname TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance NUMERIC(14,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS referral_code TEXT
    """)

    cur.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS referred_by INTEGER REFERENCES users(id)
    """)

    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS users_referral_code_unique
        ON users(referral_code)
    """)

    cur.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE
    """)
    cur.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS welcome_bonus_unlocked BOOLEAN NOT NULL DEFAULT FALSE

    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS site_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        )
    """)

    cur.execute("""
        INSERT INTO site_settings(setting_key, setting_value)
        VALUES ('withdrawals_open', 'true')
        ON CONFLICT (setting_key) DO NOTHING
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS investments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            plan TEXT NOT NULL,
            amount NUMERIC(14,2) NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            type TEXT NOT NULL,
            amount NUMERIC(14,2) NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id SERIAL PRIMARY KEY,
            referrer_id INTEGER REFERENCES users(id),
            referred_id INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(referred_id)
        )
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            bank_name TEXT NOT NULL,
            account_name TEXT NOT NULL,
            account_number TEXT NOT NULL,
            amount NUMERIC(14,2) NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        ALTER TABLE withdrawals
        ADD COLUMN IF NOT EXISTS fee_amount NUMERIC(14,2) NOT NULL DEFAULT 0
    """)
    cur.execute("""
        ALTER TABLE withdrawals
        ADD COLUMN IF NOT EXISTS payable_amount NUMERIC(14,2) NOT NULL DEFAULT 0
    """)
    cur.execute("""
        UPDATE withdrawals
        SET payable_amount = amount
        WHERE payable_amount = 0 AND amount > 0
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS deposit_requests (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            sender_name TEXT NOT NULL,
            amount NUMERIC(14,2) NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    con.commit()
    cur.close()
    con.close()


init_db()

STYLE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#180303">
<style>
*{box-sizing:border-box}
body{
 margin:0;
 font-family:Arial,sans-serif;
 background:#180303;
 color:white;
}
header{
 padding:22px 7%;
 display:flex;
 justify-content:space-between;
 align-items:center;
 background:#290606;
 border-bottom:1px solid #b98a28;
}
.logo{
 font-size:27px;
 font-weight:900;
 color:#ffcf55;
}
.logo span{color:white}
nav a{
 color:white;
 text-decoration:none;
 margin-left:20px;
 font-weight:bold;
}
.hero{
 padding:85px 7%;
 background:linear-gradient(120deg,#360606,#970d12,#270303);
 text-align:center;
}
.hero h1{
 font-size:clamp(40px,8vw,75px);
 color:#ffcf55;
 margin:10px 0;
}
.hero p{font-size:18px;color:#ffe7b0}
.btn{
 display:inline-block;
 padding:15px 28px;
 border-radius:30px;
 background:linear-gradient(90deg,#e4a923,#ffdf79);
 color:#310606;
 text-decoration:none;
 font-weight:900;
 border:none;
 cursor:pointer;
}
section{padding:45px 7%}
.title{text-align:center;color:#ffd05b;font-size:32px}
.plans{
 display:grid;
 grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
 gap:22px;
}
.card{
 background:linear-gradient(145deg,#390909,#160303);
 border:1px solid #c99b37;
 border-radius:18px;
 padding:27px;
 text-align:center;
 box-shadow:0 8px 30px #0008;
}
.card h2{color:#ffcf55}
.price{font-size:38px;font-weight:900}
.gold{color:#ffcf55}
footer{
 padding:30px;
 text-align:center;
 background:#290606;
 color:#d8b66b;
}
.formbox{
 max-width:440px;
 margin:55px auto;
 padding:30px;
 background:#310808;
 border:1px solid #d4a63c;
 border-radius:18px;
}
input{
 width:100%;
 padding:15px;
 margin:10px 0;
 background:#190404;
 border:1px solid #986e27;
 border-radius:8px;
 color:white;
}
button{width:100%}
a{color:#ffcf55}
@media(max-width:600px){
 header{padding:18px;flex-wrap:wrap;gap:15px}
 nav a{margin-left:8px;font-size:13px}
}

/* APEX INVEST MOBILE-FIRST RESPONSIVENESS */
html {
 width:100%;
 overflow-x:hidden;
 -webkit-text-size-adjust:100%;
}
body {
 width:100%;
 min-width:0;
 overflow-x:hidden;
}
header {
 width:100%;
 min-width:0;
 flex-wrap:wrap;
 gap:12px;
}
nav {
 display:flex;
 flex-wrap:wrap;
 gap:12px;
}
nav a {
 margin:0;
}
section {
 width:100%;
 max-width:1100px;
 margin:auto;
}
.plans {
 width:100%;
 grid-template-columns:repeat(2,minmax(0,1fr));
}
.card {
 min-width:0;
 overflow-wrap:anywhere;
}
.formbox {
 width:calc(100% - 30px);
 max-width:440px;
 margin:30px auto;
 padding:22px;
}
input,button,.btn {
 max-width:100%;
 min-height:46px;
 font-size:16px;
}
img {
 max-width:100%;
 height:auto;
}
@media(max-width:600px) {
 header {
  padding:16px;
  justify-content:center;
  text-align:center;
 }
 .logo {
  width:100%;
  font-size:25px;
 }
 nav {
  width:100%;
  justify-content:center;
 }
 nav a {
  font-size:13px;
  padding:8px 5px;
 }
 .hero {
  padding:55px 18px;
 }
 .hero h1 {
  font-size:39px;
  line-height:1.12;
  letter-spacing:-1px;
 }
 .hero p {
  font-size:15px;
  line-height:1.6;
 }
 section {
  padding:30px 15px;
 }
 .title {
  font-size:25px;
 }
 .plans {
  grid-template-columns:1fr;
  gap:16px;
 }
 .card {
  padding:23px 16px;
 }
 .price {
  font-size:34px;
  overflow-wrap:anywhere;
 }
 .formbox {
  padding:20px;
  margin:25px auto;
 }
 footer {
  padding:25px 15px;
  font-size:13px;
  line-height:1.7;
 }
}
@media(min-width:400px) and (max-width:600px) {
 .plans {
  grid-template-columns:repeat(2,minmax(0,1fr));
 }
 .price {
  font-size:29px;
 }
}


/* APEX INVEST: COMPLETE MOBILE DISPLAY FIX */
html, body {
 width:100%;
 max-width:100%;
 margin:0;
 padding:0;
 overflow-x:hidden;
}

body {
 font-size:16px;
}

* {
 box-sizing:border-box;
}

header {
 width:100%;
 padding:18px 5%;
}

section {
 width:100%;
 max-width:1200px;
 margin:auto;
}

.hero {
 width:100%;
 padding:85px 5%;
}

.hero h1 {
 font-size:clamp(38px, 6vw, 68px);
 line-height:1.15;
}

.hero p {
 font-size:18px;
 line-height:1.6;
}

.plans {
 width:100%;
}

.card {
 min-width:0;
}

.formbox {
 width:calc(100% - 32px);
 max-width:460px;
}

input {
 font-size:16px;
 min-height:52px;
}

.btn {
 min-height:48px;
}

@media screen and (max-width:900px) {
 header {
  padding:18px 16px;
  gap:15px;
 }

 .logo {
  font-size:27px;
 }

 nav {
  display:flex;
  justify-content:center;
  flex-wrap:wrap;
  gap:16px;
 }

 nav a {
  margin:0;
  font-size:15px;
  padding:8px 2px;
 }

 .hero {
  padding:85px 20px;
 }

 .hero h1 {
  font-size:clamp(38px, 8vw, 58px);
 }

 .hero p {
  font-size:17px;
 }

 section {
  padding:45px 20px;
 }

 .title {
  font-size:30px;
 }

 .plans {
  grid-template-columns:1fr;
  gap:22px;
 }

 .card {
  padding:30px 18px;
 }

 .price {
  font-size:40px;
 }

 .formbox {
  margin:35px auto;
  padding:25px 20px;
 }
}

@media screen and (max-width:380px) {
 .hero h1 {
  font-size:36px;
 }

 .logo {
  font-size:23px;
 }

 nav {
  gap:12px;
 }

 .price {
  font-size:34px;
 }
}
\n</style>\n</head>\n<body>
"""


@app.route("/")
def home():
    return render_template_string(STYLE + """
    <style>
    .apex-nav{display:flex;align-items:center;justify-content:space-between;gap:15px}
    .apex-nav .brand{font-size:27px;font-weight:900;color:#ffd45e}
    .apex-nav .brand span{color:white}
    .nav-actions{display:flex;gap:12px;align-items:center}
    .nav-actions a{padding:12px 20px;border-radius:25px;text-decoration:none}
    .nav-login{border:1px solid #e9bb50;color:#ffe2a0}
    .nav-register{background:linear-gradient(90deg,#d99a20,#ffe18a);color:#350707}
    .hero-main{padding:85px 6%;text-align:center;background:radial-gradient(ellipse at top,#a61919,#520707 60%,#210303)}
    .hero-tag{display:inline-block;border:1px solid #e5b84b;color:#ffe08b;padding:10px 20px;border-radius:30px;font-size:13px;letter-spacing:2px}
    .hero-main h1{font-size:clamp(38px,7vw,76px);line-height:1.12;color:#ffdc79;margin:25px auto;max-width:900px}
    .hero-main h1 span{color:white}
    .hero-description{max-width:700px;margin:0 auto;color:#f4d8c0;font-size:18px;line-height:1.9}
    .hero-buttons{display:flex;justify-content:center;gap:15px;flex-wrap:wrap;margin-top:32px}
    .hero-buttons a{padding:16px 27px;border-radius:30px;text-decoration:none;font-weight:bold}
    .primary-gold{background:linear-gradient(110deg,#d99b20,#ffe68e);color:#310505}
    .secondary-red{border:1px solid #f4ce72;color:#ffe2a0}
    .trust-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;max-width:1000px;margin:-25px auto 0;position:relative;padding:0 20px}
    .trust-item{background:#300808;border:1px solid #946d2c;border-radius:14px;padding:23px 12px;text-align:center}
    .trust-item strong{display:block;color:#ffda73;font-size:22px;margin-bottom:7px}
    .trust-item span{font-size:13px;color:#e5c9a7}
    .content-section{padding:65px 6%;max-width:1200px;margin:auto}
    .section-heading{text-align:center;color:#ffda73;font-size:34px;margin-bottom:12px}
    .section-sub{text-align:center;color:#d6bca7;line-height:1.8;max-width:700px;margin:0 auto 35px}
    .feature-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
    .feature-box{background:linear-gradient(145deg,#3d0a0a,#1e0303);border:1px solid #8c6429;border-radius:16px;padding:25px}
    .feature-icon{font-size:30px}
    .feature-box h3{color:#ffdb77}
    .feature-box p{color:#d9c4b0;line-height:1.8;font-size:14px}
    .plan-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px}
    .plan-box{background:linear-gradient(145deg,#480b0b,#210303);border:1px solid #d2a33d;border-radius:20px;padding:30px;text-align:center}
    .plan-box h3{color:#ffdc75;font-size:24px}
    .plan-price{font-size:clamp(30px,5vw,43px);font-weight:900;color:white;margin:15px 0}
    .plan-box p{color:#e2c7aa;line-height:1.8}
    .plan-box a{display:inline-block;margin-top:12px;padding:14px 24px;border-radius:25px;background:linear-gradient(90deg,#d99a20,#ffe18a);color:#300505;text-decoration:none;font-weight:bold}
    .notice{background:#2d0909;border-left:4px solid #d7a43a;padding:18px;color:#e4c9aa;line-height:1.8;margin-top:25px;font-size:13px}
    .final-cta{text-align:center;padding:55px 20px;background:linear-gradient(120deg,#650909,#a91c1c,#390606)}
    .final-cta h2{color:#ffdb75;font-size:32px}
    .final-cta p{color:#f3d8c0;line-height:1.8}
    .final-cta a{display:inline-block;margin-top:15px;padding:15px 30px;border-radius:30px;background:#ffdc75;color:#300505;text-decoration:none;font-weight:bold}
    
    .welcome-investment-section {
      position:relative;
      overflow:hidden;
      padding:55px 18px;
      background:linear-gradient(135deg,#250303,#740b0b,#280303);
      isolation:isolate;
    }
    .welcome-investment-section:before {
      content:"";
      position:absolute;
      inset:-30px;
      background:
        radial-gradient(circle at 20% 30%,#d99a2055,transparent 35%),
        radial-gradient(circle at 80% 65%,#ff252555,transparent 40%);
      filter:blur(22px);
      z-index:-1;
    }
    .growth-decoration {
      position:absolute;
      inset:0;
      z-index:-1;
      opacity:.16;
      filter:blur(3px);
      background:
        linear-gradient(145deg,transparent 45%,#ffd45e 46%,transparent 48%),
        repeating-linear-gradient(90deg,transparent 0 65px,#ffdc75 66px 68px,transparent 69px 100px);
    }
    .welcome-plans {
      max-width:720px;
      margin:30px auto;
      display:flex;
      flex-direction:column;
      gap:22px;
    }
    .welcome-plan {
      background:linear-gradient(140deg,#520909dd,#210303ee);
      border:1px solid #e5b84b;
      border-radius:22px;
      padding:28px 22px;
      text-align:center;
      box-shadow:0 0 24px #d99a2033;
    }
    .welcome-plan h3 {
      color:#ffdc75;
      font-size:27px;
      margin:5px;
    }
    .welcome-plan .plan-amount {
      color:white;
      font-size:36px;
      font-weight:900;
      margin:15px 0;
    }
    .welcome-plan p {
      color:#f1d7b7;
      line-height:1.8;
    }
    .welcome-plan a {
      display:inline-block;
      margin-top:12px;
      padding:14px 30px;
      border-radius:30px;
      background:linear-gradient(90deg,#d99a20,#ffe18a);
      color:#300505;
      text-decoration:none;
      font-weight:bold;
    }
    .withdrawal-notice {
      max-width:680px;
      margin:25px auto 0;
      padding:20px;
      text-align:center;
      color:#ffe5a0;
      background:#300707dd;
      border:1px solid #dca52f;
      border-radius:15px;
      font-size:18px;
      font-weight:bold;
    }
    .investment-disclaimer {
      max-width:680px;
      margin:15px auto 0;
      color:#e7cbb0;
      text-align:center;
      font-size:12px;
      line-height:1.7;
    }

    .apex-footer{text-align:center;padding:30px 15px;background:#200404;color:#c9aa7c;font-size:13px;line-height:1.9}
    @media(max-width:700px){
      .apex-nav{flex-direction:column;text-align:center}
      .apex-nav .brand{font-size:25px}
      .nav-actions{justify-content:center;flex-wrap:wrap}
      .hero-main{padding:65px 18px}
      .hero-main h1{font-size:42px}
      .hero-description{font-size:15px}
      .trust-strip{grid-template-columns:1fr;margin:0;padding:20px 16px}
      .trust-item{padding:17px}
      .content-section{padding:42px 16px}
      .section-heading{font-size:27px}
      .feature-grid{grid-template-columns:1fr}
      .plan-grid{grid-template-columns:1fr}
      .final-cta h2{font-size:27px}
    }
    </style>

    <header class="apex-nav">
      <div class="brand">APEX <span>INVEST</span></div>
      <div class="nav-actions">
        <a href="/" class="nav-login">Home</a>
        <a href="/login" class="nav-login">Login</a>
        <a href="/register" class="nav-register">Create Account</a>
      </div>
    </header>

    <main>
      <section class="hero-main">
        <div class="hero-tag">WELCOME TO APEX INVEST</div>
        <h1>Build Your Financial Future.<br><span>Invest With Purpose.</span></h1>
        <p class="hero-description">
          Welcome to APEX INVEST, a platform designed to make your
          investment journey simple, organized and accessible.
          Explore investment opportunities, monitor your account
          activities and take informed steps towards your financial goals.
        </p>
        <div class="hero-buttons">
          <a href="/register" class="primary-gold">GET STARTED →</a>
          <a href="/login" class="secondary-red">LOGIN TO ACCOUNT</a>
        </div>
      </section>

      <div class="trust-strip">
        <div class="trust-item"><strong>01</strong><span>Simple Registration</span></div>
        <div class="trust-item"><strong>02</strong><span>Account Monitoring</span></div>
        <div class="trust-item"><strong>03</strong><span>Investment Information</span></div>
      </div>

      

    
      <section class="welcome-investment-section">
        <div class="growth-decoration"></div>

        <h2 class="section-heading">Explore Our Investment Plans</h2>
        <p class="section-sub">
          Review the available plans and their conditions before participating.
        </p>

        <div class="welcome-plans">
          <div class="welcome-plan">
            <h3>VIP 1</h3>
            <div class="plan-amount">₦3,000</div>
            <p>Entry investment plan</p>
            <p>Advertised daily figure: <strong style="color:#ffdc75">₦200</strong></p>
            <a href="/register">EXPLORE VIP 1</a>
          </div>

          <div class="welcome-plan">
            <h3>VIP 2</h3>
            <div class="plan-amount">₦6,000</div>
            <p>Higher entry investment plan</p>
            <p>Advertised daily figure: <strong style="color:#ffdc75">₦400</strong></p>
            <a href="/register">EXPLORE VIP 2</a>
          </div>
        </div>

        <div class="withdrawal-notice">
          MINIMUM WITHDRAWAL: ₦400
        </div>

      </section>
</main>

    <footer class="apex-footer">
      <b>APEX INVEST</b><br>
      Invest Wisely • Build Your Future<br>
      © 2026 APEX INVEST. All rights reserved.
    </footer>
    """)


@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        phone = request.form.get("phone", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        referral_code = request.form.get("referral_code", "").strip().upper()

        if not all([fullname, phone, username, password]):
            flash("Complete all registration fields.")
            return redirect("/register")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect("/register")

        con = db()
        cur = con.cursor()

        try:
            referrer_id = None

            if referral_code:
                cur.execute(
                    "SELECT id FROM users WHERE UPPER(referral_code)=%s",
                    (referral_code,)
                )
                referrer = cur.fetchone()

                if not referrer:
                    con.rollback()
                    flash("Invalid referral code. Please check it.")
                    return redirect("/register")

                referrer_id = referrer[0]

            referral_code_new = secrets.token_hex(5).upper()
            email = secrets.token_hex(12) + "@noemail.apexinvest"

            cur.execute("""
                INSERT INTO users
                    (fullname, email, phone, username, password,
                     balance, referral_code, referred_by)
                VALUES (%s, %s, %s, %s, %s, 400, %s, %s)
                RETURNING id
            """, (
                fullname, email, phone, username,
                generate_password_hash(password),
                referral_code_new, referrer_id
            ))

            new_user_id = cur.fetchone()[0]

            if referrer_id:
                cur.execute("""
                    INSERT INTO referrals(referrer_id, referred_id)
                    VALUES (%s, %s)
                """, (referrer_id, new_user_id))

            cur.execute("""
                INSERT INTO transactions(user_id, type, amount, status)
                VALUES(%s, %s, %s, %s)
            """, (new_user_id, "Welcome Bonus", 400, "completed"))

            con.commit()
            flash("Account created successfully. Your referral code is " +
                  referral_code_new + ". Please login.")
            return redirect("/login")

        except psycopg2.IntegrityError:
            con.rollback()
            flash("Username already exists. Please choose another.")
        except Exception:
            con.rollback()
            app.logger.exception("Registration failed")
            flash("Registration failed. Please try again.")
        finally:
            cur.close()
            con.close()

    return render_template_string(STYLE + """
    <style>
    .auth-page{min-height:80vh;padding:35px 16px 55px;background:radial-gradient(circle at top,#690e0e,#190303 65%)}
    .auth-card{max-width:470px;width:100%;margin:20px auto;background:linear-gradient(145deg,#3b0909,#200404);border:1px solid #bd9037;border-radius:22px;padding:32px;box-shadow:0 15px 45px #0007}
    .auth-brand{text-align:center;color:#ffda75;font-size:27px;font-weight:900}
    .auth-card h1{text-align:center;color:#ffe09a;font-size:30px;margin:20px 0 8px}
    .auth-intro{text-align:center;color:#d9bda0;line-height:1.7;font-size:14px;margin-bottom:24px}
    .auth-card label{display:block;color:#f3d9ad;font-size:14px;margin:15px 0 7px}
    .auth-card input{width:100%;padding:15px;background:#190303;border:1px solid #805c2b;border-radius:10px;color:white;font-size:16px;outline:none}
    .auth-card input:focus{border-color:#ffdb76;box-shadow:0 0 0 2px #ffdb7622}
    .auth-submit{width:100%;margin-top:23px;padding:16px;border:0;border-radius:30px;background:linear-gradient(100deg,#d99b23,#ffe58b);color:#310505;font-weight:900;font-size:16px;cursor:pointer}
    .auth-bottom{text-align:center;color:#d9bda0;margin-top:22px;font-size:14px}
    .auth-bottom a{color:#ffdc79;font-weight:bold;text-decoration:none}
    .auth-message{padding:12px;background:#5b1111;border-radius:9px;color:#ffe1b1;margin:12px 0}
    .auth-back{text-align:center;margin-top:20px}
    .auth-back a{color:#e7c47d;text-decoration:none}
    @media(max-width:480px){.auth-card{padding:25px 19px}.auth-card h1{font-size:27px}}
    </style>
    <main class="auth-page">
      <div class="auth-card">
        <div class="auth-brand">APEX INVEST</div>
        <h1>Create Your Account</h1>
        <p class="auth-intro">Join APEX INVEST and take the first step
        towards a more organized investment experience.</p>

        {% with messages=get_flashed_messages() %}
          {% for m in messages %}<div class="auth-message">{{m}}</div>{% endfor %}
        {% endwith %}

        <form method="POST">
          <label>Full Name</label>
          <input name="fullname" placeholder="Enter your full name" autocomplete="name" required>

          <label>Phone Number</label>
          <input name="phone" type="tel" placeholder="Enter your phone number" autocomplete="tel" required>

          <label>Choose Username</label>
          <input name="username" placeholder="Create a username" autocomplete="username" required>

          <label>Create Password</label>
          <input name="password" type="password" placeholder="At least 8 characters" minlength="8" autocomplete="new-password" required>

          <label>Referral Code (optional)</label>
          <input name="referral_code" value="{{ request.args.get('ref', '')|e }}" placeholder="Enter your friend's referral code" autocomplete="off">

          <button class="auth-submit" type="submit">CREATE MY ACCOUNT →</button>
        </form>

        <div class="auth-bottom">
          Already have an account? <a href="/login">Login here</a>
        </div>
        <div class="auth-back"><a href="/">← Back to homepage</a></div>
      </div>
    </main>
    """)


@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        identity = request.form.get("identity","").strip()
        password = request.form.get("password","")

        con = db()
        cur = con.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM users
            WHERE username=%s OR email=%s
        """,(identity,identity.lower()))
        user = cur.fetchone()
        cur.close()
        con.close()

        if user and check_password_hash(user["password"],password):
            if user.get("is_banned", False):
                flash("Your account has been suspended. Please contact support.")
                return redirect("/login")

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/dashboard")

        flash("Incorrect username, email or password.")

    return render_template_string(STYLE + """
    <style>
    .auth-page{min-height:80vh;padding:45px 16px 65px;background:radial-gradient(circle at top,#720f0f,#190303 65%)}
    .auth-card{max-width:440px;width:100%;margin:35px auto;background:linear-gradient(145deg,#3b0909,#200404);border:1px solid #bd9037;border-radius:22px;padding:34px;box-shadow:0 15px 45px #0007}
    .auth-brand{text-align:center;color:#ffda75;font-size:28px;font-weight:900}
    .auth-card h1{text-align:center;color:#ffe09a;font-size:31px;margin:24px 0 8px}
    .auth-intro{text-align:center;color:#d9bda0;line-height:1.8;font-size:14px;margin-bottom:27px}
    .auth-card label{display:block;color:#f3d9ad;font-size:14px;margin:16px 0 8px}
    .auth-card input{width:100%;padding:16px;background:#190303;border:1px solid #805c2b;border-radius:10px;color:white;font-size:16px;outline:none}
    .auth-card input:focus{border-color:#ffdb76;box-shadow:0 0 0 2px #ffdb7622}
    .auth-submit{width:100%;margin-top:25px;padding:16px;border:0;border-radius:30px;background:linear-gradient(100deg,#d99b23,#ffe58b);color:#310505;font-weight:900;font-size:16px;cursor:pointer}
    .auth-bottom{text-align:center;color:#d9bda0;margin-top:25px;font-size:14px}
    .auth-bottom a{color:#ffdc79;font-weight:bold;text-decoration:none}
    .auth-message{padding:12px;background:#5b1111;border-radius:9px;color:#ffe1b1;margin:12px 0}
    .auth-back{text-align:center;margin-top:22px}
    .auth-back a{color:#e7c47d;text-decoration:none}
    @media(max-width:480px){.auth-card{padding:27px 20px}.auth-card h1{font-size:27px}}
    </style>
    <main class="auth-page">
      <div class="auth-card">
        <div class="auth-brand">APEX INVEST</div>
        <h1>Welcome Back</h1>
        <p class="auth-intro">Sign in securely to access your account,
        review your activity and manage your investment information.</p>

        {% with messages=get_flashed_messages() %}
          {% for m in messages %}<div class="auth-message">{{m}}</div>{% endfor %}
        {% endwith %}

        <form method="POST">
          <label>Username or Email</label>
          <input name="identity" placeholder="Enter username or email" autocomplete="username" required>

          <label>Password</label>
          <input name="password" type="password" placeholder="Enter your password" autocomplete="current-password" required>

          <button class="auth-submit" type="submit">LOGIN TO MY ACCOUNT →</button>
        </form>

        <div class="auth-bottom">
          Don't have an account? <a href="/register">Register now</a>
        </div>
        <div class="auth-back"><a href="/">← Back to homepage</a></div>
      </div>
    </main>
    """)




@app.route("/referrals")
def referrals():
    if not session.get("user_id"):
        return redirect("/login")

    con = db()
    cur = con.cursor()

    try:
        user_id = session["user_id"]

        cur.execute(
            "SELECT referral_code FROM users WHERE id=%s",
            (user_id,)
        )
        user = cur.fetchone()

        if not user:
            flash("Account not found.")
            return redirect("/login")

        referral_code = user[0]

        if not referral_code:
            referral_code = secrets.token_hex(5).upper()
            cur.execute(
                "UPDATE users SET referral_code=%s WHERE id=%s",
                (referral_code, user_id)
            )

        cur.execute("""
            CREATE TABLE IF NOT EXISTS referral_commissions (
                id SERIAL PRIMARY KEY,
                investment_id INTEGER NOT NULL REFERENCES investments(id),
                investor_id INTEGER NOT NULL REFERENCES users(id),
                beneficiary_id INTEGER NOT NULL REFERENCES users(id),
                level INTEGER NOT NULL,
                rate NUMERIC(5,2) NOT NULL,
                amount NUMERIC(14,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(investment_id, level)
            )
        """)

        cur.execute("""
            SELECT COUNT(*)
            FROM referrals
            WHERE referrer_id=%s
        """, (user_id,))
        direct_count = cur.fetchone()[0]

        cur.execute("""
            SELECT level, COALESCE(SUM(amount), 0)
            FROM referral_commissions
            WHERE beneficiary_id=%s
            GROUP BY level
        """, (user_id,))
        earnings = {int(row[0]): float(row[1]) for row in cur.fetchall()}

        level1 = earnings.get(1, 0)
        level2 = earnings.get(2, 0)
        level3 = earnings.get(3, 0)
        total = level1 + level2 + level3

        referral_link = request.host_url.rstrip("/") + "/register?ref=" + referral_code

        cur.execute("""
            SELECT u.username, r.created_at
            FROM referrals r
            JOIN users u ON u.id=r.referred_id
            WHERE r.referrer_id=%s
            ORDER BY r.created_at DESC
        """, (user_id,))
        referral_list = cur.fetchall()

        con.commit()

        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>My Referrals - APEX INVEST</title>
            <style>
                * { box-sizing:border-box; }
                body {
                    margin:0; padding:20px;
                    background:#07111d; color:#fff;
                    font-family:Arial,sans-serif;
                }
                .container { max-width:650px; margin:25px auto; }
                .card {
                    background:#102235; border:1px solid #23435b;
                    border-radius:15px; padding:20px;
                    margin-bottom:16px;
                }
                h1 { color:#39e6a0; }
                .code {
                    font-size:25px; font-weight:bold;
                    color:#39e6a0; letter-spacing:3px;
                    overflow-wrap:anywhere;
                }
                .link {
                    width:100%; padding:12px; border-radius:8px;
                    border:1px solid #34536b; background:#07111d;
                    color:white; margin:10px 0;
                }
                button, .back {
                    display:inline-block; padding:13px 18px;
                    border:0; border-radius:8px;
                    background:#16b981; color:#061b16;
                    font-weight:bold; text-decoration:none;
                    cursor:pointer;
                }
                .stats {
                    display:grid; grid-template-columns:1fr 1fr;
                    gap:12px;
                }
                .stat {
                    background:#0a1928; padding:15px;
                    border-radius:10px;
                }
                .stat strong {
                    display:block; color:#39e6a0;
                    font-size:22px; margin-top:8px;
                }
                .muted { color:#a9bac9; }
                .person {
                    padding:12px 0;
                    border-bottom:1px solid #294154;
                }
            </style>
        </head>
        <body>
        <div class="container">
            <h1>My Referrals</h1>
            <p class="muted">Invite people using your personal referral link.</p>

            <div class="card">
                <p class="muted">Your referral code</p>
                <div class="code">{{ code }}</div>
                <p class="muted">Your referral link</p>
                <input class="link" id="refLink" value="{{ link }}" readonly>
                <button onclick="copyLink()">Copy Referral Link</button>
                <p id="copyMessage" class="muted"></p>
            </div>

            <div class="card">
                <h3>Referral Earnings</h3>
                <div class="stats">
                    <div class="stat">Level 1 (20%)<strong>₦{{ "%.2f"|format(l1) }}</strong></div>
                    <div class="stat">Level 2 (3%)<strong>₦{{ "%.2f"|format(l2) }}</strong></div>
                    <div class="stat">Level 3 (2%)<strong>₦{{ "%.2f"|format(l3) }}</strong></div>
                    <div class="stat">Total Earnings<strong>₦{{ "%.2f"|format(total) }}</strong></div>
                    <div class="stat">Direct Referrals<strong>{{ count }}</strong></div>
                </div>
                <p class="muted" style="margin-top:18px;padding:14px;background:#0a1928;border-radius:10px;line-height:1.6">
                    💰 <strong>Wallet Information:</strong> All referral commissions are automatically credited to your normal account balance. You do not have a separate referral wallet.
                </p>
            </div>

            <div class="card">
                <h3>People You Referred</h3>
                {% if people %}
                    {% for person in people %}
                    <div class="person">
                        <strong>{{ person[0] }}</strong><br>
                        <span class="muted">{{ person[1] }}</span>
                    </div>
                    {% endfor %}
                {% else %}
                    <p class="muted">You have not referred anyone yet.</p>
                {% endif %}
            </div>

            <a class="back" href="/dashboard">Back to Dashboard</a>
        </div>

        <script>
        function copyLink() {
            const field = document.getElementById("refLink");
            field.select();
            field.setSelectionRange(0, 99999);
            try {
                document.execCommand("copy");
                document.getElementById("copyMessage").textContent =
                    "Referral link copied!";
            } catch (e) {
                document.getElementById("copyMessage").textContent =
                    "Please copy the link manually.";
            }
        }
        </script>
        </body>
        </html>
        """,
        code=referral_code,
        link=referral_link,
        count=direct_count,
        l1=level1,
        l2=level2,
        l3=level3,
        total=total,
        people=referral_list)

    except Exception:
        con.rollback()
        app.logger.exception("Referral page failed")
        flash("Could not load referrals. Please try again.")
        return redirect("/dashboard")
    finally:
        cur.close()
        con.close()


@app.route("/dashboard")
def dashboard():
    if not session.get("user_id"):
        return redirect("/login")

    con = db()
    cur = con.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
    user = cur.fetchone()
    cur.close()
    con.close()

    if not user:
        session.clear()
        return redirect("/login")

    return render_template_string(STYLE + """
    <style>
    .dash-wrap{
        max-width:1100px;
        margin:auto;
        padding:25px 16px 55px;
    }
    .dash-top{
        display:flex;
        justify-content:space-between;
        align-items:center;
        gap:12px;
        padding:18px;
        background:linear-gradient(120deg,#650707,#210202);
        border:1px solid #dca52f;
        border-radius:17px;
        box-shadow:0 0 18px #ff202044;
    }
    .dash-logo{
        color:#ffdc76;
        font-size:24px;
        font-weight:900;
        text-shadow:0 0 12px #ffbd35;
    }
    .dash-logout{
        padding:11px 19px;
        border-radius:25px;
        color:white;
        background:linear-gradient(120deg,#a90000,#ff2424);
        border:1px solid #ffb84d;
        text-decoration:none;
        font-weight:bold;
        box-shadow:0 0 13px #ff222277;
    }
    .dash-welcome{
        margin:28px 0 18px;
        color:#ffe19a;
        font-size:27px;
        text-shadow:0 0 13px #e5a52b88;
    }
    .balance-card{
        padding:27px;
        border-radius:20px;
        background:linear-gradient(135deg,#850b0b,#260303 75%);
        border:2px solid #e5b342;
        box-shadow:0 0 15px #ff303055,0 0 30px #d99b2355;
    }
    .balance-label{color:#f8dca1;font-size:15px}
    .balance-number{
        color:#ffdf79;
        font-size:36px;
        font-weight:900;
        margin-top:10px;
        text-shadow:0 0 16px #ffb52c;
        overflow-wrap:anywhere;
    }
    .section-title{
        color:#ffdf83;
        font-size:22px;
        margin:32px 0 17px;
    }
    .plan-grid,.action-grid{
        display:grid;
        grid-template-columns:repeat(2,minmax(0,1fr));
        gap:17px;
    }
    .vip-card{
        background:linear-gradient(145deg,#720808,#260303);
        border:2px solid #e7b744;
        border-radius:19px;
        padding:23px 17px;
        text-align:center;
        box-shadow:0 0 13px #ff282844,0 0 24px #e7a52b33;
    }
    .vip-name{
        color:#ffe18a;
        font-size:23px;
        font-weight:900;
    }
    .vip-price{
        color:white;
        font-size:30px;
        font-weight:900;
        margin:15px 0 8px;
    }
    .vip-reward{
        color:#ffdc60;
        font-size:17px;
        font-weight:bold;
    }
    .glow-btn{
        display:flex;
        align-items:center;
        justify-content:center;
        text-align:center;
        min-height:57px;
        padding:14px 10px;
        border-radius:13px;
        background:linear-gradient(110deg,#a80000,#f12626,#a80000);
        border:1px solid #ffdc78;
        color:white;
        text-decoration:none;
        font-size:15px;
        font-weight:900;
        box-shadow:0 0 10px #ff252566,0 0 19px #ff252533;
        transition:.2s;
    }
    .glow-btn.gold{
        background:linear-gradient(110deg,#b77b12,#ffe18a,#c58a20);
        color:#390500;
        box-shadow:0 0 12px #ffc34288,0 0 22px #ffc34233;
    }
    .glow-btn:active{transform:scale(.97)}
    .action-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
    .dash-note{
        margin-top:25px;
        padding:17px;
        border:1px solid #a8792c;
        border-radius:13px;
        color:#e9d3a5;
        background:#350606;
        font-size:13px;
        line-height:1.7;
    }
    @media(max-width:650px){
        .dash-wrap{padding:15px 12px 40px}
        .dash-logo{font-size:20px}
        .dash-welcome{font-size:23px}
        .plan-grid{grid-template-columns:1fr}
        .action-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
        .balance-number{font-size:30px}
        .vip-price{font-size:27px}
    }
    @media(prefers-reduced-motion:no-preference){
        .vip-card{animation:goldGlow 3s ease-in-out infinite alternate}
        @keyframes goldGlow{
            from{box-shadow:0 0 9px #ff282833,0 0 15px #e7a52b22}
            to{box-shadow:0 0 17px #ff282266,0 0 27px #e7a52b55}
        }
    }
    </style>

    <main class="dash-wrap">
      <div class="dash-top">
        <div class="dash-logo">✦ APEX INVEST</div>
        <a class="dash-logout" href="/logout">LOGOUT ↗</a>
      </div>

      <h1 class="dash-welcome">Welcome, {{user.username}} 👋</h1>

      <div class="balance-card">
        <div class="balance-label">YOUR AVAILABLE BALANCE</div>
        <div class="balance-number">₦{{"{:,.2f}".format(user.balance)}}</div>
      </div>

      <a class="glow-btn gold" href="https://t.me/Apexinvestsite"
         target="_blank" rel="noopener noreferrer"
         style="display:block;text-align:center;margin:18px 0 25px;padding:16px">
         ✈ JOIN OUR TELEGRAM GROUP
      </a>

      <h2 class="section-title">✦ Account Activities</h2>

      <div class="action-grid">
        <a class="glow-btn gold" href="/daily-rewards">🎁 Claim Daily Reward</a>
        <a class="glow-btn" href="/deposit">💳 Deposit</a>
        <a class="glow-btn" href="/withdraw">💸 Withdraw</a>
        <a class="glow-btn gold" href="/referrals">👥 Referrals</a>
        <a class="glow-btn" href="/history">📜 History</a>
        <a class="glow-btn" href="/investments">⭐ My Investments</a>
      </div>

      <h2 class="section-title">✦ Choose Your Investment Plan</h2>

      <div class="plan-grid">
        <div class="vip-card">
          <div class="vip-name">VIP 1</div>
          <div class="vip-price">₦3,000</div>
          <div class="vip-reward">Advertised daily figure: ₦200</div>
          <p style="color:#e9cba0">View plan details and terms</p>
          <form method="POST" action="/activate-plan">
            <input type="hidden" name="plan" value="VIP 1">
            <button class="glow-btn gold" style="width:100%;cursor:pointer">ACTIVATE VIP 1</button>
          </form>
        </div>

        <div class="vip-card">
          <div class="vip-name">VIP 2</div>
          <div class="vip-price">₦6,000</div>
          <div class="vip-reward">Advertised daily figure: ₦400</div>
          <p style="color:#e9cba0">View plan details and terms</p>
          <form method="POST" action="/activate-plan">
            <input type="hidden" name="plan" value="VIP 2">
            <button class="glow-btn gold" style="width:100%;cursor:pointer">ACTIVATE VIP 2</button>
          </form>
        </div>
      </div>

    </main>
    """, user=user)



@app.route("/activate-plan", methods=["POST"])
def activate_plan():
    if not session.get("user_id"):
        return redirect("/login")

    plans = {
        "VIP 1": (3000, 200),
        "VIP 2": (6000, 400)
    }

    plan = request.form.get("plan", "").strip()

    if plan not in plans:
        flash("Invalid investment plan.")
        return redirect("/dashboard")

    amount, daily_reward = plans[plan]
    con = db()
    cur = con.cursor()

    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referral_commissions (
                id SERIAL PRIMARY KEY,
                investment_id INTEGER NOT NULL REFERENCES investments(id),
                investor_id INTEGER NOT NULL REFERENCES users(id),
                beneficiary_id INTEGER NOT NULL REFERENCES users(id),
                level INTEGER NOT NULL,
                rate NUMERIC(5,2) NOT NULL,
                amount NUMERIC(14,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(investment_id, level)
            )
        """)

        cur.execute(
            "SELECT balance, referred_by FROM users WHERE id=%s FOR UPDATE",
            (session["user_id"],)
        )
        row = cur.fetchone()

        if not row:
            con.rollback()
            flash("Account not found.")
            return redirect("/dashboard")

        balance, sponsor_id = row
        balance = balance or 0

        if balance < amount:
            con.rollback()
            flash("Insufficient balance. Please deposit first.")
            return redirect("/dashboard")

        cur.execute(
            "UPDATE users SET balance=balance-%s WHERE id=%s",
            (amount, session["user_id"])
        )

        cur.execute("""
            INSERT INTO investments
            (user_id, plan, amount, status)
            VALUES (%s, %s, %s, 'active')
            RETURNING id
        """, (session["user_id"], plan, amount))

        investment_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO transactions
            (user_id, type, amount, status)
            VALUES (%s, %s, %s, 'completed')
        """, (
            session["user_id"],
            "Investment activation - " + plan,
            -amount
        ))

        # Three-level referral commissions: 20%, 3%, and 2%.
        rates = [20, 3, 2]
        current_sponsor = sponsor_id
        visited = {session["user_id"]}
        paid_levels = 0

        for level, rate in enumerate(rates, start=1):
            if not current_sponsor or current_sponsor in visited:
                break

            visited.add(current_sponsor)
            commission = round(float(amount) * rate / 100, 2)

            cur.execute("""
                INSERT INTO referral_commissions
                (investment_id, investor_id, beneficiary_id, level, rate, amount)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (investment_id, level) DO NOTHING
                RETURNING id
            """, (
                investment_id,
                session["user_id"],
                current_sponsor,
                level,
                rate,
                commission
            ))

            commission_row = cur.fetchone()

            if commission_row:
                cur.execute("""
                    UPDATE users
                    SET balance = balance + %s
                    WHERE id = %s
                """, (commission, current_sponsor))

                cur.execute("""
                    INSERT INTO transactions
                    (user_id, type, amount, status)
                    VALUES (%s, %s, %s, 'completed')
                """, (
                    current_sponsor,
                    "Referral commission - Level " + str(level),
                    commission
                ))

                paid_levels += 1

            cur.execute(
                "SELECT referred_by FROM users WHERE id=%s",
                (current_sponsor,)
            )
            sponsor_row = cur.fetchone()
            current_sponsor = sponsor_row[0] if sponsor_row else None

        cur.execute("""
            UPDATE users
            SET welcome_bonus_unlocked = TRUE
            WHERE id = %s
        """, (session["user_id"],))

        con.commit()
        flash(plan + " activation successful! Referral commissions processed. Your welcome bonus is now unlocked.")

    except Exception:
        con.rollback()
        app.logger.exception("Investment activation failed")
        flash("Activation failed. Please try again.")
    finally:
        cur.close()
        con.close()

    return redirect("/dashboard")


@app.route("/daily-rewards", methods=["GET", "POST"])
def daily_rewards():
    if not session.get("user_id"):
        return redirect("/login")

    con = db()
    cur = con.cursor(cursor_factory=RealDictCursor)
    message = ""

    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_reward_claims (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                investment_id INTEGER REFERENCES investments(id),
                amount NUMERIC(14,2) NOT NULL,
                claim_date DATE DEFAULT CURRENT_DATE,
                status TEXT DEFAULT 'completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(investment_id, claim_date)
            )
        """)
        con.commit()

        if request.method == "POST":
            investment_id = request.form.get("investment_id", "")

            cur.execute("""
                SELECT id, plan
                FROM investments
                WHERE id=%s AND user_id=%s AND status='active'
                FOR UPDATE
            """, (investment_id, session["user_id"]))

            investment = cur.fetchone()

            if not investment:
                message = "Active investment not found."
            else:
                rewards = {"VIP 1": 200, "VIP 2": 400}
                reward = rewards.get(investment["plan"])

                if reward is None:
                    message = "Invalid investment plan."
                else:
                    cur.execute("""
                        SELECT created_at
                        FROM daily_reward_claims
                        WHERE investment_id=%s
                        ORDER BY created_at DESC
                        LIMIT 1
                        FOR UPDATE
                    """, (investment["id"],))

                    last_claim = cur.fetchone()

                    if last_claim:
                        cur.execute("""
                            SELECT
                              created_at + INTERVAL '24 hours' <= CURRENT_TIMESTAMP AS eligible,
                              GREATEST(0, EXTRACT(EPOCH FROM (
                                created_at + INTERVAL '24 hours' - CURRENT_TIMESTAMP
                              )))::INTEGER AS seconds_left
                            FROM daily_reward_claims
                            WHERE investment_id=%s
                            ORDER BY created_at DESC
                            LIMIT 1
                        """, (investment["id"],))

                        timing = cur.fetchone()

                        if not timing["eligible"]:
                            hours = timing["seconds_left"] // 3600
                            minutes = (timing["seconds_left"] % 3600) // 60
                            message = f"Please wait {hours} hours and {minutes} minutes before claiming again."
                        else:
                            last_claim = None

                    if not last_claim or message == "":
                        cur.execute("""
                            INSERT INTO daily_reward_claims
                            (user_id, investment_id, amount, status)
                            VALUES (%s, %s, %s, 'completed')
                            RETURNING id
                        """, (session["user_id"], investment["id"], reward))

                        cur.execute("""
                            UPDATE users
                            SET balance = balance + %s
                            WHERE id=%s
                        """, (reward, session["user_id"]))

                        cur.execute("""
                            INSERT INTO transactions
                            (user_id, type, amount, status)
                            VALUES (%s, %s, %s, 'completed')
                        """, (
                            session["user_id"],
                            "Daily reward - " + investment["plan"],
                            reward
                        ))

                        con.commit()
                        message = f"Congratulations! ₦{reward:,.2f} has been added to your balance."

        cur.execute("""
            SELECT id, plan, amount, created_at
            FROM investments
            WHERE user_id=%s AND status='active'
            ORDER BY created_at DESC
        """, (session["user_id"],))
        investments = cur.fetchall()

        cur.execute("""
            SELECT investment_id, amount, status, created_at
            FROM daily_reward_claims
            WHERE user_id=%s
            ORDER BY created_at DESC
            LIMIT 20
        """, (session["user_id"],))
        claims = cur.fetchall()

        cur.execute("SELECT balance FROM users WHERE id=%s", (session["user_id"],))
        balance_row = cur.fetchone()
        balance = balance_row["balance"] if balance_row else 0

        return render_template_string(STYLE + """
        <main style="max-width:750px;margin:30px auto;padding:18px;color:#ffe19a">
          <h1>🎁 Daily Rewards</h1>
          <div style="background:#390606;border:1px solid #dca52f;padding:18px;border-radius:14px">
            <p>AVAILABLE BALANCE</p>
            <h2>₦{{"{:,.2f}".format(balance)}}</h2>
          </div>

          {% if message %}
          <div style="padding:15px;background:#450909;border:1px solid #e5b342;border-radius:12px;margin:15px 0">
            {{message}}
          </div>
          {% endif %}

          {% for inv in investments %}
          <div style="background:#390606;border:1px solid #dca52f;border-radius:15px;padding:20px;margin:15px 0">
            <h2>{{inv.plan}}</h2>
            <h3>Daily reward: ₦{{"{:,.2f}".format(200 if inv.plan == "VIP 1" else 400)}}</h3>
            <p>One successful claim every 24 hours.</p>
            <form method="POST">
              <input type="hidden" name="investment_id" value="{{inv.id}}">
              <button style="padding:14px;width:100%;border:1px solid #ffdc78;border-radius:10px;background:#a80000;color:white;font-weight:bold">
                CLAIM DAILY REWARD
              </button>
            </form>
          </div>
          {% else %}
          <p>You do not have an active investment plan.</p>
          {% endfor %}

          <h2>Recent Reward Claims</h2>
          {% for claim in claims %}
            <p>₦{{"{:,.2f}".format(claim.amount)}} — {{claim.status|upper}} — {{claim.created_at}}</p>
          {% else %}
            <p>No reward claims yet.</p>
          {% endfor %}

          <a href="/dashboard" style="color:#ffdc78">← Back to dashboard</a>
        </main>
        """, investments=investments, claims=claims, balance=balance)

    except Exception:
        con.rollback()
        app.logger.exception("Daily reward error")
        return "Daily reward error. Check your Termux terminal.", 500
    finally:
        cur.close()
        con.close()


@app.route("/investments")
def my_investments():
    if not session.get("user_id"):
        return redirect("/login")

    con = db()
    cur = con.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT id, plan, amount, status, created_at
            FROM investments
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (session["user_id"],))

        investments = cur.fetchall()

        return render_template_string(STYLE + """
        <main style="max-width:850px;margin:30px auto;padding:18px;color:#ffe19a">
            <h1 style="text-align:center">⭐ My Investments</h1>
            <p style="text-align:center;color:#ddd">
                View your activated investment plans.
            </p>

            {% for inv in investments %}
            <div style="background:#390606;border:1px solid #dca52f;
                        border-radius:16px;padding:22px;margin:18px 0;
                        box-shadow:0 0 15px #7b3900">

                <h2 style="color:#ffdc78">{{ inv.plan }}</h2>

                <p>Amount paid:
                    <strong>₦{{ "{:,.2f}".format(inv.amount) }}</strong>
                </p>

                <p>Activation date: {{ inv.created_at }}</p>

                <p>Status:
                    <strong style="color:#7dff9b">
                        {{ inv.status|upper }}
                    </strong>
                </p>

                {% if inv.status == "active" %}
                <p style="color:#7dff9b">✓ Your plan is active.</p>
                {% endif %}
            </div>
            {% else %}
            <div style="background:#390606;border:1px solid #dca52f;
                        border-radius:14px;padding:25px;text-align:center">
                <h3>No investment plan activated yet.</h3>
                <p>Choose VIP 1 or VIP 2 from your dashboard to get started.</p>
            </div>
            {% endfor %}

            <a href="/dashboard" style="display:block;text-align:center;
               color:#ffdc78;margin-top:25px">
                ← Back to Dashboard
            </a>
        </main>
        """, investments=investments)

    except Exception:
        app.logger.exception("My investments page error")
        return "Unable to load investments. Check your Termux terminal.", 500

    finally:
        cur.close()
        con.close()


@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    if not session.get("user_id"):
        return redirect("/login")

    con = db()
    cur = con.cursor()
    try:
        cur.execute(
            "SELECT is_banned FROM users WHERE id=%s",
            (session["user_id"],)
        )
        account = cur.fetchone()
        if not account or account[0]:
            session.clear()
            flash("Your account is suspended.")
            return redirect("/login")

        cur.execute(
            "SELECT setting_value FROM site_settings WHERE setting_key='withdrawals_open'"
        )
        setting = cur.fetchone()
        withdrawals_open = bool(setting and setting[0] == "true")
    finally:
        cur.close()
        con.close()

    if not withdrawals_open:
        return render_template_string(
            STYLE + "<main style='max-width:500px;margin:60px auto;padding:25px;color:#ffe19a;text-align:center'><h2>Withdrawals Temporarily Closed</h2><p>New withdrawal requests are currently unavailable. Please check again later.</p><a href='/dashboard'>Back to Dashboard</a></main>"
        )

    message = None
    success = False

    if request.method == "POST":
        bank = request.form.get("bank_name", "").strip()
        account_name = request.form.get("account_name", "").strip()
        account_number = request.form.get("account_number", "").strip()
        amount_text = request.form.get("amount", "").strip()

        try:
            from decimal import Decimal, InvalidOperation
            amount = Decimal(amount_text)
            if not amount.is_finite() or amount < Decimal("400"):
                raise ValueError()
        except (InvalidOperation, ValueError):
            message = "Minimum withdrawal is ₦400. Enter a valid amount."

        if not message and (
            not bank or not account_name
            or not account_number.isdigit()
            or not 6 <= len(account_number) <= 20
        ):
            message = "Please enter valid bank and account details."

        if not message:
            con = db()
            cur = con.cursor()
            try:
                cur.execute(
                    "SELECT balance, welcome_bonus_unlocked FROM users WHERE id=%s FOR UPDATE",
                    (session["user_id"],)
                )
                row = cur.fetchone()

                if not row:
                    message = "Account not found. Please login again."
                elif not row[1]:
                    message = "Activate a plan first to unlock your ₦400 welcome bonus."
                else:
                    balance = Decimal(str(row[0] or 0))

                    if amount > balance:
                        message = "Insufficient available balance."
                    else:
                        cur.execute("""
                            UPDATE users
                            SET balance = balance - %s
                            WHERE id = %s AND balance >= %s
                        """, (amount, session["user_id"], amount))

                        if cur.rowcount != 1:
                            message = "Insufficient available balance."
                        else:
                            from decimal import ROUND_HALF_UP
                            amount = amount.quantize(Decimal("0.01"))
                            fee_amount = (amount * Decimal("0.10")).quantize(
                                Decimal("0.01"), rounding=ROUND_HALF_UP
                            )
                            payable_amount = amount - fee_amount

                            cur.execute("""
                                INSERT INTO withdrawals
                                (user_id, bank_name, account_name,
                                 account_number, amount, fee_amount,
                                 payable_amount, status)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,'pending')
                            """, (
                                session["user_id"], bank, account_name,
                                account_number, amount, fee_amount,
                                payable_amount
                            ))
                            con.commit()
                            success = True
                            message = (
                                f"Request submitted! Requested: ₦{amount:,.2f} | "
                                f"10% fee: ₦{fee_amount:,.2f} | "
                                f"You will receive: ₦{payable_amount:,.2f}. "
                                "Awaiting admin approval."
                            )

            except Exception:
                con.rollback()
                raise
            finally:
                cur.close()
                con.close()

    return render_template_string(STYLE + """
    <style>
    .withdraw-page{
        max-width:540px;
        margin:35px auto;
        padding:20px 15px 50px;
    }
    .withdraw-card{
        background:linear-gradient(145deg,#700808,#210303);
        border:2px solid #e4b343;
        border-radius:22px;
        padding:27px 22px;
        box-shadow:0 0 18px #ff222244,0 0 28px #e7a52b33;
    }
    .withdraw-card h1{
        color:#ffdf80;
        text-align:center;
        font-size:27px;
    }
    .withdraw-min{
        text-align:center;
        background:#390606;
        color:#ffdf80;
        border:1px solid #dca43b;
        padding:14px;
        border-radius:12px;
        font-weight:bold;
        margin:20px 0;
    }
    .withdraw-card label{
        display:block;
        color:#ffe1a1;
        margin:17px 0 8px;
        font-weight:bold;
    }
    .withdraw-card input{
        width:100%;
        min-width:0;
        padding:15px;
        border-radius:10px;
        border:1px solid #b98a37;
        background:#190303;
        color:white;
        font-size:16px;
    }
    .withdraw-submit{
        width:100%;
        padding:16px;
        margin-top:24px;
        border:1px solid #ffe18b;
        border-radius:30px;
        background:linear-gradient(100deg,#a90000,#f12a2a);
        color:white;
        font-size:16px;
        font-weight:900;
        box-shadow:0 0 15px #ff292966;
    }
    .withdraw-message{
        padding:13px;
        margin:15px 0;
        border-radius:10px;
        background:#4a0909;
        color:#ffe3a2;
        text-align:center;
    }
    .withdraw-back{
        display:block;
        text-align:center;
        margin-top:22px;
        color:#ffdf80;
        text-decoration:none;
    }
    </style>

    <main class="withdraw-page">
      <div class="withdraw-card">
        <h1>💸 Withdraw Funds</h1>
        <p style="text-align:center;color:#e9cba0">
          Enter your correct bank details to request a withdrawal.
        </p>

        <div class="withdraw-min">
          MINIMUM WITHDRAWAL<br>
          <span style="font-size:27px">₦400</span><br>
          Applies to VIP 1 and VIP 2
        </div>

        {% if message %}
          <div class="withdraw-message">{{message}}</div>
        {% endif %}

        <form method="POST">
          <label>Bank Name</label>
          <input name="bank_name" placeholder="e.g. Opay, Access Bank"
                 autocomplete="off" required>

          <label>Account Name</label>
          <input name="account_name" placeholder="Enter account name"
                 autocomplete="name" required>

          <label>Account Number</label>
          <input name="account_number" type="text" inputmode="numeric"
                 pattern="[0-9]{6,20}" maxlength="20"
                 placeholder="Enter account number" required>

          <label>Withdrawal Amount (₦)</label>
          <input name="amount" type="number" min="400" step="0.01"
                 placeholder="Minimum ₦400" required>

          <button class="withdraw-submit" type="submit">
            SUBMIT WITHDRAWAL REQUEST →
          </button>
        </form>

        <a class="withdraw-back" href="/dashboard">
          ← Back to Dashboard
        </a>
      </div>
    </main>
    """, message=message, success=success)



@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    if not session.get("user_id"):
        return redirect("/login")

    message = ""

    if request.method == "POST":
        sender = request.form.get("sender_name", "").strip()
        amount_text = request.form.get("amount", "").strip()

        from decimal import Decimal, InvalidOperation

        try:
            amount = Decimal(amount_text)
            if not amount.is_finite() or amount <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            message = "Enter a valid deposit amount."
        else:
            if not sender:
                message = "Enter the sender's name."
            elif len(sender) > 100:
                message = "Sender name is too long."
            else:
                con = db()
                cur = con.cursor()
                try:
                    cur.execute("""
                        INSERT INTO deposit_requests
                        (user_id, sender_name, amount, status)
                        VALUES (%s, %s, %s, 'pending')
                    """, (session["user_id"], sender, amount))
                    con.commit()
                    message = "Deposit submitted successfully. Awaiting admin verification."
                except Exception:
                    con.rollback()
                    raise
                finally:
                    cur.close()
                    con.close()

    return render_template_string(STYLE + """
    <style>
    .deposit-page{max-width:540px;margin:30px auto;padding:18px 14px 45px}
    .deposit-card{
      background:linear-gradient(145deg,#710707,#210303);
      border:2px solid #e6b643;border-radius:22px;padding:25px 20px;
      box-shadow:0 0 18px #ff252544,0 0 25px #e5a52b33;
    }
    .deposit-card h1{text-align:center;color:#ffdf80}
    .account-box{
      background:#300505;border:1px solid #d9a53d;
      border-radius:15px;padding:19px;margin:20px 0;
    }
    .account-box p{color:#e8cda0;margin:12px 0}
    .account-box strong{color:#ffdf80}
    .account-number{
      font-size:27px;font-weight:900;color:#fff;
      letter-spacing:1px;overflow-wrap:anywhere
    }
    .deposit-card label{display:block;color:#ffe0a0;margin:17px 0 8px}
    .deposit-card input{
      width:100%;padding:15px;border-radius:10px;
      border:1px solid #b88a36;background:#190303;
      color:white;font-size:16px
    }
    .deposit-submit{
      width:100%;padding:16px;margin-top:23px;border:1px solid #ffe18b;
      border-radius:30px;background:linear-gradient(100deg,#a90000,#f22b2b);
      color:white;font-weight:900;font-size:16px;
      box-shadow:0 0 15px #ff292966
    }
    .deposit-message{
      background:#470909;color:#ffe2a0;padding:13px;
      border-radius:10px;margin:15px 0;line-height:1.5
    }
    .deposit-back{display:block;text-align:center;margin-top:20px;color:#ffdf80}
    </style>

    <main class="deposit-page">
      <div class="deposit-card">
        <h1>💳 Make a Deposit</h1>
        <p style="text-align:center;color:#e9cba0">
          Transfer to the account below, then submit your payment details.
        </p>

        <div class="account-box">
          <p>PAYMENT METHOD</p>
          <h2 style="color:#ffdf80;margin:5px 0">OPay</h2>
          <p>ACCOUNT NAME</p>
          <strong>CHIDERE MUORAH</strong>
          <p>ACCOUNT NUMBER</p>
          <div class="account-number">6157389257</div>
          <p style="font-size:13px">Please confirm the account details before transferring.</p>
        </div>

        {% if message %}
          <div class="deposit-message">{{message}}</div>
        {% endif %}

        <form method="POST">
          <label>Sender's Name</label>
          <input name="sender_name" placeholder="Name used to make payment"
                 maxlength="100" required>

          <label>Amount Sent (₦)</label>
          <input name="amount" type="number" min="1" step="0.01"
                 placeholder="Enter amount sent" required>

          <button class="deposit-submit" type="submit">
            SUBMIT DEPOSIT →
          </button>
        </form>

        <a class="deposit-back" href="/dashboard">← Back to Dashboard</a>
      </div>
    </main>
    """, message=message)



@app.route("/history")
def history():
    if not session.get("user_id"):
        return redirect("/login")

    con = db()
    cur = con.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT 'Deposit' AS activity, amount, status, created_at,
                   sender_name AS details
            FROM deposit_requests
            WHERE user_id=%s

            UNION ALL

            SELECT 'Withdrawal' AS activity, amount, status, created_at,
                   bank_name || ' - ' || account_name AS details
            FROM withdrawals
            WHERE user_id=%s

            UNION ALL

            SELECT type AS activity, amount, status, created_at,
                   type AS details
            FROM transactions
            WHERE user_id=%s

            ORDER BY created_at DESC
            LIMIT 100
        """, (
            session["user_id"],
            session["user_id"],
            session["user_id"]
        ))

        records = cur.fetchall()

        return render_template_string(STYLE + """
        <main style="max-width:900px;margin:30px auto;padding:18px;color:#ffe19a">
          <h1>📜 Account History</h1>
          <p>Deposits, withdrawals, investments and reward activities.</p>

          {% for item in records %}
          <div style="background:#390606;border:1px solid #dca52f;border-radius:13px;padding:17px;margin:13px 0">
            <h3>{{item.activity}}</h3>
            <p>Amount: ₦{{"{:,.2f}".format(item.amount)}}</p>
            <p>Details: {{item.details}}</p>
            <p>Status: <strong>{{item.status|upper}}</strong></p>
            <small>{{item.created_at}}</small>
          </div>
          {% else %}
          <p>No account activities yet.</p>
          {% endfor %}

          <a href="/dashboard" style="color:#ffdc78">← Back to dashboard</a>
        </main>
        """, records=records)

    except Exception:
        app.logger.exception("History page error")
        return "Could not load account history. Check the terminal.", 500
    finally:
        cur.close()
        con.close()


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    import hmac

    message = ""

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        correct_username = "Apexinvest"
        correct_password = "Apex@50"

        if not correct_username or not correct_password:
            message = "Admin credentials have not been configured."
        elif (
            hmac.compare_digest(username, correct_username)
            and hmac.compare_digest(password, correct_password)
        ):
            session["admin_logged_in"] = True
            return redirect("/admin/dashboard")
        else:
            message = "Incorrect admin username or password."

    return render_template_string(STYLE + """
    <main style="max-width:430px;margin:55px auto;padding:20px;color:#ffe19a">
      <div style="background:linear-gradient(145deg,#710707,#210303);
      border:2px solid #e5b342;border-radius:20px;padding:25px;
      box-shadow:0 0 22px #ff252544">
        <h1 style="text-align:center;color:#ffdf80">✦ APEX ADMIN</h1>
        <p style="text-align:center">Administrator Login</p>

        {% if message %}
        <p style="background:#4b0808;padding:12px;border-radius:9px">
          {{message}}
        </p>
        {% endif %}

        <form method="POST">
          <label>Admin Username</label>
          <input name="username" required
          style="width:100%;padding:14px;margin:10px 0;background:#190303;
          color:white;border:1px solid #dca52f;border-radius:9px">

          <label>Admin Password</label>
          <input type="password" name="password" required
          style="width:100%;padding:14px;margin:10px 0;background:#190303;
          color:white;border:1px solid #dca52f;border-radius:9px">

          <button style="width:100%;padding:15px;margin-top:15px;
          background:#a90000;color:white;border:1px solid #ffdc78;
          border-radius:12px;font-weight:bold">
            LOGIN TO ADMIN
          </button>
        </form>
      </div>
    </main>
    """, message=message)


@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect("/admin")

    con = db()
    cur = con.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("SELECT COUNT(*) AS total FROM users")
        total_users = cur.fetchone()["total"]

        cur.execute("""
            SELECT id, fullname, username, phone, is_banned
            FROM users
            ORDER BY created_at DESC
            LIMIT 200
        """)
        managed_users = cur.fetchall()

        cur.execute("""
            SELECT setting_value FROM site_settings
            WHERE setting_key='withdrawals_open'
        """)
        setting = cur.fetchone()
        withdrawals_open = bool(setting and setting["setting_value"] == "true")

        cur.execute("""
            SELECT COUNT(*) AS total
            FROM deposit_requests WHERE status='pending'
        """)
        pending_deposits = cur.fetchone()["total"]

        cur.execute("""
            SELECT COUNT(*) AS total
            FROM withdrawals WHERE status='pending'
        """)
        pending_withdrawals = cur.fetchone()["total"]

        cur.execute("""
            SELECT d.id, d.sender_name, d.amount, d.status,
                   d.created_at, u.username, u.fullname
            FROM deposit_requests d
            JOIN users u ON u.id=d.user_id
            ORDER BY d.created_at DESC
            LIMIT 100
        """)
        deposits = cur.fetchall()

        cur.execute("""
            SELECT w.id, w.bank_name, w.account_name,
                   w.account_number, w.amount, w.fee_amount,
                   w.payable_amount, w.status,
                   w.created_at, u.username, u.fullname
            FROM withdrawals w
            JOIN users u ON u.id=w.user_id
            ORDER BY w.created_at DESC
            LIMIT 100
        """)
        withdrawals = cur.fetchall()

        return render_template_string(STYLE + """
        <style>
        body {
            background: #080808;
        }

        .admin-wrap {
            max-width: 1200px;
            margin: auto;
            padding: 22px 15px 60px;
        }

        .admin-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
            padding: 23px;
            border: 1px solid #d9aa4d;
            border-radius: 20px;
            background:
              radial-gradient(circle at right,#a0000033,transparent 45%),
              linear-gradient(120deg,#390707,#100505);
            box-shadow: 0 0 25px #b0000033;
        }

        .admin-brand {
            color: #ffdc83;
            font-size: 25px;
            font-weight: 1000;
            letter-spacing: 1px;
            text-shadow: 0 0 15px #dba83e;
        }

        .admin-subtitle {
            color: #bba98a;
            font-size: 12px;
            margin-top: 7px;
        }

        .admin-logout {
            padding: 12px 20px;
            border-radius: 30px;
            background: linear-gradient(120deg,#850000,#ed2525);
            border: 1px solid #ffda7a;
            color: white;
            text-decoration: none;
            font-weight: 900;
            font-size: 12px;
        }

        .admin-welcome {
            color: #ffdf8b;
            font-size: 25px;
            margin: 30px 0 7px;
        }

        .admin-description {
            color: #a99b83;
            font-size: 13px;
            margin-bottom: 22px;
        }

        .admin-stats {
            display: grid;
            grid-template-columns: repeat(3,minmax(0,1fr));
            gap: 16px;
            margin: 22px 0 30px;
        }

        .stat {
            position: relative;
            overflow: hidden;
            padding: 23px 18px;
            border: 1px solid #bd8b36;
            border-radius: 18px;
            background: linear-gradient(145deg,#490909,#170505);
            box-shadow: 0 0 20px #a0000025;
        }

        .stat:nth-child(2) {
            background: linear-gradient(145deg,#59400e,#1b1005);
        }

        .stat:nth-child(3) {
            background: linear-gradient(145deg,#3c1010,#160505);
        }

        .stat-icon {
            font-size: 25px;
        }

        .stat p {
            color: #d5bd91;
            font-size: 11px;
            font-weight: 900;
            letter-spacing: 1px;
            margin: 13px 0 5px;
        }

        .stat h2 {
            color: #ffdf80;
            font-size: 36px;
            margin: 0;
            font-weight: 1000;
        }

        .admin-section {
            margin-top: 27px;
            padding: 21px;
            border: 1px solid #805d2c;
            border-radius: 19px;
            background: linear-gradient(145deg,#1d0808,#100606);
            box-shadow: 0 0 20px #a000001b;
        }

        .section-heading {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 18px;
        }

        .section-heading h2 {
            color: #ffdf80;
            font-size: 20px;
            margin: 0;
        }

        .section-count {
            color: #ffda80;
            background: #5a300d;
            border: 1px solid #a87a2c;
            border-radius: 30px;
            padding: 7px 12px;
            font-size: 11px;
            font-weight: 900;
        }

        .request-grid {
            display: grid;
            grid-template-columns: repeat(2,minmax(0,1fr));
            gap: 15px;
        }

        .request {
            min-width: 0;
            padding: 19px;
            border: 1px solid #704b27;
            border-radius: 16px;
            background: linear-gradient(145deg,#3a0909,#190606);
            overflow-wrap: anywhere;
        }

        .request h3 {
            color: #ffe08a;
            font-size: 18px;
            margin: 0 0 14px;
        }

        .request p {
            color: #d6c4a4;
            font-size: 13px;
            line-height: 1.6;
            margin: 7px 0;
        }

        .request strong {
            color: #ffdc83;
        }

        .request-amount {
            color: #ffdc78 !important;
            font-size: 22px !important;
            font-weight: 1000;
            margin: 13px 0 !important;
        }

        .status {
            display: inline-block;
            padding: 6px 11px;
            border-radius: 20px;
            background: #52380e;
            border: 1px solid #c29239;
            color: #ffe18c;
            font-size: 10px;
            font-weight: 1000;
        }

        .admin-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 17px;
        }

        .admin-actions form {
            flex: 1;
            min-width: 115px;
        }

        .admin-actions button {
            width: 100%;
            padding: 12px 9px;
            border: 0;
            border-radius: 10px;
            color: white;
            font-size: 11px;
            font-weight: 1000;
            cursor: pointer;
        }

        .approve {
            background: linear-gradient(120deg,#087b38,#19b75d);
            box-shadow: 0 0 12px #12a84b33;
        }

        .reject {
            background: linear-gradient(120deg,#890000,#ed2525);
            box-shadow: 0 0 12px #ed252533;
        }

        .empty-state {
            padding: 25px;
            text-align: center;
            color: #bba98a;
            border: 1px dashed #76552c;
            border-radius: 13px;
        }

        @media(max-width:700px) {
            .admin-wrap {
                padding: 13px 11px 40px;
            }

            .admin-brand {
                font-size: 20px;
            }

            .admin-stats {
                grid-template-columns: 1fr;
                gap: 11px;
            }

            .stat {
                padding: 18px;
            }

            .stat h2 {
                font-size: 30px;
            }

            .request-grid {
                grid-template-columns: 1fr;
            }

            .admin-section {
                padding: 14px;
            }

            .admin-welcome {
                font-size: 22px;
            }
        }
        </style>

        <main class="admin-wrap">

          <header class="admin-head">
            <div>
              <div class="admin-brand">✦ APEX INVEST</div>
              <div class="admin-subtitle">ADMINISTRATION CONTROL CENTER</div>
            </div>
            <a class="admin-logout" href="/admin/logout">LOGOUT ↗</a>
          </header>

          <h1 class="admin-welcome">Welcome, Administrator 👋</h1>
          <p class="admin-description">
            Monitor registered users and manage deposit and withdrawal requests.
          </p>

          <div class="admin-stats">

            <div class="stat">
              <div class="stat-icon">👥</div>
              <p>TOTAL REGISTERED USERS</p>
              <h2>{{total_users}}</h2>
            </div>

            <div class="stat">
              <div class="stat-icon">💳</div>
              <p>PENDING DEPOSITS</p>
              <h2>{{pending_deposits}}</h2>
            </div>

            <div class="stat">
              <div class="stat-icon">💸</div>
              <p>PENDING WITHDRAWALS</p>
              <h2>{{pending_withdrawals}}</h2>
            </div>

          </div>

          <section class="admin-section">
            <div class="section-heading">
              <h2>⚙️ Platform Controls</h2>
            </div>
            <p>Withdrawal status:
              <strong>{{ "OPEN" if withdrawals_open else "CLOSED" }}</strong>
            </p>
            <form method="POST" action="/admin/withdrawal-toggle">
              <input type="hidden" name="open" value="{{ 'false' if withdrawals_open else 'true' }}">
              <button class="approve" type="submit">
                {{ "CLOSE WITHDRAWALS" if withdrawals_open else "OPEN WITHDRAWALS" }}
              </button>
            </form>
          </section>

          <section class="admin-section">
            <div class="section-heading">
              <h2>👥 User Ban Management</h2>
              <span class="section-count">{{total_users}} USERS</span>
            </div>
            <div class="request-grid">
            {% for u in managed_users %}
              <div class="request">
                <h3>{{u.fullname}}</h3>
                <p><strong>Username:</strong> {{u.username}}</p>
                <p><strong>Phone:</strong> {{u.phone}}</p>
                <p><strong>Status:</strong>
                  {{ "BANNED" if u.is_banned else "ACTIVE" }}
                </p>
                <form method="POST" action="/admin/user-action">
                  <input type="hidden" name="user_id" value="{{u.id}}">
                  <input type="hidden" name="action" value="{{'unban' if u.is_banned else 'ban'}}">
                  <button class="{{'approve' if u.is_banned else 'reject'}}" type="submit">
                    {{ "UNBAN USER" if u.is_banned else "BAN USER" }}
                  </button>
                </form>
              </div>
            {% else %}
              <p>No users found.</p>
            {% endfor %}
            </div>
          </section>

          <section class="admin-section">
            <div class="section-heading">
              <h2>💳 Deposit Management</h2>
              <span class="section-count">{{pending_deposits}} PENDING</span>
            </div>

            <div class="request-grid">
            {% for d in deposits %}
              <div class="request">
                <h3>👤 {{d.fullname}}</h3>
                <p><strong>Username:</strong> {{d.username}}</p>
                <p><strong>Sender name:</strong> {{d.sender_name}}</p>
                <p class="request-amount">₦{{"{:,.2f}".format(d.amount)}}</p>
                <p><strong>Date:</strong> {{d.created_at}}</p>
                <p><strong>Status:</strong> <span class="status">{{d.status|upper}}</span></p>

                {% if d.status == 'pending' %}
                <div class="admin-actions">
                  <form method="POST" action="/admin/action">
                    <input type="hidden" name="kind" value="deposit">
                    <input type="hidden" name="request_id" value="{{d.id}}">
                    <input type="hidden" name="decision" value="approve">
                    <button class="approve">✓ APPROVE</button>
                  </form>

                  <form method="POST" action="/admin/action">
                    <input type="hidden" name="kind" value="deposit">
                    <input type="hidden" name="request_id" value="{{d.id}}">
                    <input type="hidden" name="decision" value="reject">
                    <button class="reject">✕ REJECT</button>
                  </form>
                </div>
                {% endif %}
              </div>
            {% else %}
              <div class="empty-state">No deposit requests yet.</div>
            {% endfor %}
            </div>
          </section>

          <section class="admin-section">
            <div class="section-heading">
              <h2>💸 Withdrawal Management</h2>
              <span class="section-count">{{pending_withdrawals}} PENDING</span>
            </div>

            <div class="request-grid">
            {% for w in withdrawals %}
              <div class="request">
                <h3>👤 {{w.fullname}}</h3>
                <p><strong>Username:</strong> {{w.username}}</p>
                <p><strong>Bank:</strong> {{w.bank_name}}</p>
                <p><strong>Account name:</strong> {{w.account_name}}</p>
                <p><strong>Account number:</strong> {{w.account_number}}</p>
                <p><strong>Requested:</strong> ₦{{"{:,.2f}".format(w.amount)}}</p>
                <p><strong>10% fee:</strong> ₦{{"{:,.2f}".format(w.fee_amount)}}</p>
                <p class="request-amount"><strong>Amount to pay:</strong> ₦{{"{:,.2f}".format(w.payable_amount)}}</p>
                <p><strong>Date:</strong> {{w.created_at}}</p>
                <p><strong>Status:</strong> <span class="status">{{w.status|upper}}</span></p>

                {% if w.status == 'pending' %}
                <div class="admin-actions">
                  <form method="POST" action="/admin/action">
                    <input type="hidden" name="kind" value="withdrawal">
                    <input type="hidden" name="request_id" value="{{w.id}}">
                    <input type="hidden" name="decision" value="approve">
                    <button class="approve">✓ APPROVE</button>
                  </form>

                  <form method="POST" action="/admin/action">
                    <input type="hidden" name="kind" value="withdrawal">
                    <input type="hidden" name="request_id" value="{{w.id}}">
                    <input type="hidden" name="decision" value="reject">
                    <button class="reject">✕ REJECT</button>
                  </form>
                </div>
                {% endif %}
              </div>
            {% else %}
              <div class="empty-state">No withdrawal requests yet.</div>
            {% endfor %}
            </div>
          </section>

        </main>
        """,
        total_users=total_users,
        pending_deposits=pending_deposits,
        pending_withdrawals=pending_withdrawals,
        deposits=deposits,
        withdrawals=withdrawals,
        managed_users=managed_users,
        withdrawals_open=withdrawals_open
        )

    except Exception:
        app.logger.exception("Admin dashboard error")
        return "Admin dashboard error. Check Termux terminal.", 500
    finally:
        cur.close()
        con.close()


@app.route("/admin/action", methods=["POST"])
def admin_action():
    if not session.get("admin_logged_in"):
        return redirect("/admin")

    kind = request.form.get("kind", "")
    decision = request.form.get("decision", "")
    request_id = request.form.get("request_id", "")

    if kind not in ("deposit", "withdrawal") or decision not in ("approve", "reject"):
        return redirect("/admin/dashboard")

    con = db()
    cur = con.cursor()

    try:
        table = "deposit_requests" if kind == "deposit" else "withdrawals"

        cur.execute(
            f"SELECT id, user_id, amount, status, payable_amount FROM {table} WHERE id=%s FOR UPDATE",
            (request_id,)
        )
        item = cur.fetchone()

        if not item or item[3] != "pending":
            con.rollback()
            flash("This request has already been processed.")
            return redirect("/admin/dashboard")

        request_user_id = item[1]
        amount = item[2]

        if decision == "reject":
            if kind == "withdrawal":
                cur.execute("""
                    UPDATE users
                    SET balance = balance + %s
                    WHERE id = %s
                """, (amount, request_user_id))

                cur.execute("""
                    INSERT INTO transactions (user_id, type, amount, status)
                    VALUES (%s, 'Withdrawal refund', %s, 'completed')
                """, (request_user_id, amount))

            cur.execute(
                f"UPDATE {table} SET status='rejected' WHERE id=%s AND status='pending'",
                (request_id,)
            )

            if cur.rowcount != 1:
                con.rollback()
                flash("Request status changed. Please refresh.")
                return redirect("/admin/dashboard")

            con.commit()
            return redirect("/admin/dashboard")

        cur.execute(
            "SELECT balance FROM users WHERE id=%s FOR UPDATE",
            (request_user_id,)
        )
        user = cur.fetchone()

        if not user:
            con.rollback()
            flash("User account not found.")
            return redirect("/admin/dashboard")

        if kind == "deposit":
            cur.execute(
                "UPDATE users SET balance=balance+%s WHERE id=%s",
                (amount, request_user_id)
            )
            transaction_type = "Deposit approved"
        else:
            # Withdrawal was already deducted at submission.
            transaction_type = "Withdrawal approved"

        cur.execute(
            f"UPDATE {table} SET status='approved' WHERE id=%s AND status='pending'",
            (request_id,)
        )

        if cur.rowcount != 1:
            con.rollback()
            flash("Request status changed. Please refresh.")
            return redirect("/admin/dashboard")

        transaction_amount = amount if kind == "deposit" else -item[4]

        cur.execute("""
            INSERT INTO transactions (user_id, type, amount, status)
            VALUES (%s, %s, %s, 'completed')
        """, (request_user_id, transaction_type, transaction_amount))

        con.commit()

    except Exception:
        con.rollback()
        app.logger.exception("Admin action failed")
        return "Admin action failed. Check the Termux terminal.", 500
    finally:
        cur.close()
        con.close()

    return redirect("/admin/dashboard")


@app.route("/admin/user-action", methods=["POST"])
def admin_user_action():
    if not session.get("admin_logged_in"):
        return redirect("/admin")

    action = request.form.get("action")
    user_id = request.form.get("user_id")

    if action not in ("ban", "unban") or not user_id or not user_id.isdigit():
        return redirect("/admin/dashboard")

    con = db()
    cur = con.cursor()
    try:
        cur.execute(
            "UPDATE users SET is_banned=%s WHERE id=%s",
            (action == "ban", int(user_id))
        )
        con.commit()
        flash("User " + ("banned." if action == "ban" else "unbanned."))
    except Exception:
        con.rollback()
        app.logger.exception("User ban action failed")
        flash("Could not update user status.")
    finally:
        cur.close()
        con.close()

    return redirect("/admin/dashboard")


@app.route("/admin/withdrawal-toggle", methods=["POST"])
def admin_withdrawal_toggle():
    if not session.get("admin_logged_in"):
        return redirect("/admin")

    value = request.form.get("open")
    if value not in ("true", "false"):
        return redirect("/admin/dashboard")

    con = db()
    cur = con.cursor()
    try:
        cur.execute("""
            UPDATE site_settings
            SET setting_value=%s
            WHERE setting_key='withdrawals_open'
        """, (value,))
        con.commit()
        flash("Withdrawals are now " + ("OPEN." if value == "true" else "CLOSED."))
    except Exception:
        con.rollback()
        app.logger.exception("Withdrawal toggle failed")
        flash("Could not update withdrawal settings.")
    finally:
        cur.close()
        con.close()

    return redirect("/admin/dashboard")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect("/admin")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0",port=5000,debug=False)
