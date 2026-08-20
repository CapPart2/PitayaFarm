# Deploy PITAYA on Railway

This repository deploys as one Railway service. The service contains the React
interface, disease-detection API, and yield/dashboard API, so all three share
the same database and uploaded files.

1. Commit and push this repository to GitHub.
2. In Railway, choose **New Project** > **Deploy from GitHub Repo**, then select
   `CapPart2/PitayaFarm`. Railway will detect the included `Dockerfile`.
3. Open the service **Variables** and add the values in `.env.railway.example`.
   Use a long random `ADMIN_TOKEN` and a strong `DEFAULT_ADMIN_PASSWORD`; do not
   use the sample values.
4. In **Volumes**, add a volume mounted at `/app/data`. This keeps user
   accounts, reports, and uploaded images through redeployments.
5. Deploy. Once it completes, open **Settings** > **Networking** and generate a
   public Railway domain. That single URL is the web app and its API.

## Publish the real Android APK

The APK is deliberately kept outside Git because generated Android packages can
be very large. After deploying the code above and adding the `/app/data` volume,
run this from the project root to upload the exact Android Studio build to that
persistent volume:

```powershell
$env:PITAYA_MIGRATION_URL = "https://your-railway-domain.up.railway.app"
$env:PITAYA_MIGRATION_ADMIN_TOKEN = "your-Railway-ADMIN_TOKEN"
node scripts/deploy_android_apk.mjs
```

The operation resumes safely if interrupted. Once it finishes, the landing-page
button and this public URL download that same APK:

`https://your-railway-domain.up.railway.app/downloads/app-debug.apk`

The first build downloads TensorFlow and yield-detection packages, so it may
take several minutes. Use at least 2 GB RAM; the $20 Pro plan is suitable.

Before sharing the site, sign in as `admin` using the
`DEFAULT_ADMIN_PASSWORD` you created in Railway.
