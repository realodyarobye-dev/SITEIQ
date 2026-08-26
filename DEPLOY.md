# Deploying SiteIQ — step by step, no coding required

This guide assumes you have never used GitHub or Railway. Follow it in order.
Total time: about 20 minutes. You will not write or read any code.

---

## Part 1 — Put the files on GitHub (about 6 minutes)

1. Go to **github.com** and sign in. If you do not have an account, click
   **Sign up** and make one. It is free.

2. Click the **+** in the top-right corner, then **New repository**.

3. Fill in:
   - **Repository name:** `siteiq`
   - Select **Private** (this keeps your work to yourself)
   - Do **not** tick "Add a README file"
   - Click **Create repository**

4. On the next screen, look for the link that says
   **"uploading an existing file"** and click it.

5. Unzip the SiteIQ folder on your computer. Open it. You will see files like
   `app.py`, `requirements.txt`, `Procfile`, and a folder called `siteiq`.

6. Select **everything inside that folder** — all the files AND the `siteiq`
   folder — and drag them into the browser window.

   > **Important:** drag the *contents*, not the outer folder. When it finishes,
   > GitHub should show `app.py` and `requirements.txt` at the top level of the
   > repository. If instead you see a single folder, you dragged the wrong
   > thing — delete the repository and start again at step 2.

7. Wait for all uploads to finish, then scroll down and click
   **Commit changes**.

---

## Part 2 — Deploy on Railway (about 5 minutes)

1. Go to **railway.app** and click **Login**, then
   **Login with GitHub**. Approve the permissions it asks for.

2. Click **New Project**.

3. Choose **Deploy from GitHub repo**.

4. Pick your `siteiq` repository. If it does not appear, click
   **Configure GitHub App** and give Railway access to it.

5. Railway starts building immediately. Wait 2–3 minutes. You will see log text
   scrolling. When it says **Success** or the status turns green, it is built.

6. Click your service, go to the **Settings** tab, scroll to **Networking**,
   and click **Generate Domain**.

7. Railway gives you a web address like `siteiq-production-a1b2.up.railway.app`.
   **Open it.** SiteIQ is live.

Bookmark that address on your iPad home screen. In Safari, tap the share button
and choose **Add to Home Screen** — it then opens like an app.

---

## Part 3 — Keep your saved reports (2 minutes, important)

By default Railway erases everything each time you redeploy, which means your
saved reports and calibration data disappear. Fix it once:

1. In Railway, click your service.
2. Click the **Variables** tab, then look for the **+ New** button and choose
   **Volume** (it may be under the service's right-click menu as *Attach Volume*).
3. Set the **Mount path** to exactly: `/data`
4. Save. Railway redeploys automatically.

SiteIQ detects `/data` on its own and starts saving there. Nothing else to do.

---

## Part 4 — Add your Google key (5 minutes, biggest upgrade)

SiteIQ works without this. But without it you get no competitor star ratings,
no review counts, no opening hours, no photos and no Street View — which is
roughly half of what makes competitor intelligence useful.

### Get the key

1. Go to **console.cloud.google.com** and sign in with any Google account.
2. At the top, click the project dropdown, then **New Project**. Name it
   `SiteIQ`. Click **Create**. Wait a few seconds, then select it.
3. In the search bar at the top, search for and enable each of these three,
   one at a time (search the name, click it, click **Enable**):
   - **Places API (New)**
   - **Geocoding API**
   - **Street View Static API**
4. Search for **Credentials** in the top search bar and open it.
5. Click **+ Create Credentials**, then **API key**.
6. Copy the long string it shows you. That is your key.
7. You will be asked to set up billing. Google requires a card on file even
   for free usage. There is a monthly free credit that covers normal use — a
   single location report costs roughly 5 to 15 cents, and SiteIQ caches every
   response for a week so re-opening a report or downloading its PDF is free.

   > If you want a hard safety net, in Google Cloud go to **Billing → Budgets
   > & alerts** and set a budget of $20/month with an email alert.

### Put the key into Railway

1. In Railway, click your service, then the **Variables** tab.
2. Click **+ New Variable**.
3. **Name:** `GOOGLE_MAPS_API_KEY`
   **Value:** paste your key
4. Click **Add**. Railway redeploys automatically. Wait a minute.

Open SiteIQ and go to **Setup** in the top menu. It should now say
**CONNECTED**.

**Never paste your key into a chat, an email, or a public web page.** SiteIQ
keeps it on the server — it is never sent to your browser.

---

## Part 5 — Two more free variables worth setting

In Railway → Variables → **+ New Variable**, add these:

| Name | Value | Why |
|---|---|---|
| `CONTACT_EMAIL` | your email address | OpenStreetMap's free address lookup asks apps to identify themselves. Without this you risk being rate-limited. |
| `SECRET_KEY` | any long random string you make up | Used to sign session data. Just mash the keyboard for 40 characters. |
| `NYC_APP_TOKEN` | *(optional)* | Free from data.cityofnewyork.us. Raises the NYC records rate limit so comparing 15 addresses at once does not get throttled. |

---

## Using it

1. Open your Railway address on your iPad.
2. Type an address. Pick the business type. Press **Investigate this location**.
3. Wait 20–60 seconds while it works. It shows you what it is doing.
4. Read the top of the report — that is your 20-second answer. Scroll for depth.
5. Tap **Download PDF report** or **Download PowerPoint**. On an iPad both save
   straight to Files and open in Safari, Word or Keynote.

**Do this first, before anything else:** go to **Calibrate** in the top menu and
enter two or three of your existing stores with their real average daily sales.
SiteIQ compares its estimate against your actual numbers and corrects every
future report for that business type. It turns a generic model into one anchored
to how you actually run a store. It is the highest-value ten minutes you can
spend in this app.

---

## When something goes wrong

**The page says "Application failed to respond"**
Railway is still building, or the build failed. In Railway click your service →
**Deployments** → click the newest one → read the log. The most common cause is
that files were uploaded inside a folder instead of at the top level. `app.py`
must sit at the root of the repository.

**"Could not locate the address"**
Add the borough and state: `352 9th Ave, New York, NY` rather than `352 9th Ave`.

**Competitors have no ratings or photos**
The Google key is missing or an API is not enabled. Check **Setup** in the top
menu, then re-check that all three APIs from Part 4 are enabled.

**The analysis is slow or times out**
OpenStreetMap's free servers are occasionally busy. SiteIQ automatically tries
three different mirrors. Wait a minute and try again.

**My saved reports vanished**
You have not attached the `/data` volume. See Part 3.

**I want to update SiteIQ later**
Upload the changed files to the same GitHub repository. Railway notices and
redeploys within a minute, on its own.

---

## What this costs to run

| Item | Cost |
|---|---|
| Railway hosting | About $5/month on their starter plan |
| Volume storage | Pennies |
| OpenStreetMap, U.S. Census, NYC Open Data | Free, no key |
| Google Maps APIs | Free credit covers light use; roughly 5–15 cents per new location |

Realistically you should expect around **$5–15/month** unless you run hundreds
of new locations.
