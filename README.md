# Barbie Bitch Cult Tweet Resurrector
Listen up, queens and chaos agents: this script is your digital Ouija board for summoning tweets that certain people really wish had stayed dead. It digs through the Internet Archive (Wayback Machine), hunts down deleted posts and their attached images, then politely resurrects the original text, timestamp, and archive URL into a clean CSV while dumping the pics into whatever folder you crown as home. No more “that never happened” gaslighting. The receipts are back, baby.

# Legal Disclaimer (because we’re chaotic, not stupid):
This tool is for archival and research purposes only. Respect robots.txt where applicable, follow all local laws, and don’t be a creep or a criminal with it. Don’t use this for harassment, doxxing, or anything that would make Karma side-eye you. Use responsibly.


# The Twitter Archive Scraper

The Twitter Archive Scraper is an interactive command-line tool that searches the
Internet Archive for preserved Twitter/X tweets from a handle, saves the tweet
date/text/archive link into a CSV file, and downloads any preserved tweet images
that it can find.

This project is designed for people who are not technical. You do not need to
install any Python packages. You only need Python 3.10 or newer.

## What You Need

- A computer running Windows, macOS, or Linux
- Internet access
- Python 3.10 or newer
- This project folder

The script uses only Python's built-in libraries. There is no `pip install`
step.

## Download The Project

### Easiest Method: Download ZIP

1. Go to the project page:
   [The-Barbie-Bitch-Cult/archived-twitter-scraper](https://github.com/The-Barbie-Bitch-Cult/archived-twitter-scraper)
2. Click the green `Code` button.
3. Click `Download ZIP`.
4. Find the downloaded ZIP file on your computer.
5. Right-click it and choose `Extract All` on Windows, or double-click it on
   macOS.
6. You should now have a folder named something like
   `archived-twitter-scraper-main`.

### Optional Method: Git

Use this only if you already know what Git is.

```bash
git clone https://github.com/The-Barbie-Bitch-Cult/archived-twitter-scraper.git
cd archived-twitter-scraper
```

## Windows Setup

### 1. Install Python

1. Open this page in your browser:
   [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Click the button to download Python for Windows.
3. Open the downloaded installer.
4. On the first installer screen, check the box that says:
   `Add python.exe to PATH`
5. Click `Install Now`.
6. When installation finishes, close the installer.

### 2. Check That Python Works

1. Press the `Windows` key.
2. Type `PowerShell`.
3. Open `Windows PowerShell`.
4. Type this command and press Enter:

```powershell
py --version
```

You should see something like:

```text
Python 3.12.5
```

Any Python version `3.10` or newer is fine.

### 3. Open The Project Folder In PowerShell

1. Open the folder where you extracted this project.
2. Click the address bar at the top of File Explorer.
3. Type `powershell` and press Enter.
4. PowerShell should open inside the project folder.

If that does not work, open PowerShell manually and use `cd` to move into the
folder. Example:

```powershell
cd Downloads\archived-twitter-scraper-main
```

### 4. Run The Scraper On Windows

```powershell
py twitter_archive_scraper.py
```

## macOS Setup

### 1. Install Python

1. Open this page in your browser:
   [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Download the macOS Python installer.
3. Open the downloaded `.pkg` file.
4. Follow the installer steps.
5. When installation finishes, close the installer.

### 2. Check That Python Works

1. Open `Terminal`.
   - Press `Command + Space`.
   - Type `Terminal`.
   - Press Enter.
2. Type this command and press Enter:

```bash
python3 --version
```

You should see something like:

```text
Python 3.12.5
```

Any Python version `3.10` or newer is fine.

### 3. Open The Project Folder In Terminal

If the project is in your Downloads folder, this command will usually work:

```bash
cd ~/Downloads/archived-twitter-scraper-main
```

If your folder has a different name, type `cd ` with a space after it, then drag
the project folder into the Terminal window and press Enter.

### 4. Run The Scraper On macOS

```bash
python3 twitter_archive_scraper.py
```

## Linux Setup

Many Linux computers already have Python installed.

### 1. Check Whether Python Is Already Installed

Open a terminal and run:

```bash
python3 --version
```

If you see Python `3.10` or newer, you can skip to `Run The Scraper On Linux`.

### 2. Install Python On Ubuntu, Debian, Linux Mint, Or Pop!_OS

```bash
sudo apt update
sudo apt install python3
```

Then check the version:

```bash
python3 --version
```

### 3. Install Python On Fedora

```bash
sudo dnf install python3
```

Then check the version:

```bash
python3 --version
```

### 4. Install Python On Arch Linux

```bash
sudo pacman -S python
```

Then check the version:

```bash
python3 --version
```

### 5. Open The Project Folder In Terminal

If the project is in your Downloads folder, this command will usually work:

```bash
cd ~/Downloads/archived-twitter-scraper-main
```

If your folder has a different name, type `cd ` with a space after it, then drag
the project folder into the Terminal window and press Enter.

### 6. Run The Scraper On Linux

```bash
python3 twitter_archive_scraper.py
```

## Using The Interactive Scraper

When the script starts, it asks several questions.

### Twitter handle

Type the account name without the `@`.

Example:

```text
uwu_underground
```

### Output CSV filename

This is the spreadsheet file the script will create.

Example:

```text
uwu_underground_tweets.csv
```

You can open this CSV later in Excel, Google Sheets, LibreOffice Calc, or Numbers.

### Folder where tweet images should be saved

This is where downloaded tweet images will go.

Example:

```text
uwu_underground_images
```

If the folder does not exist, the script creates it.

### Delay in seconds

This tells the script to pause between tweet requests. The Internet Archive can
be slow or rate-limited.

Recommended beginner value:

```text
0.5
```

For very large accounts, `1`, `3`, `5`, or `10` may be safer.

### Max-tweets

Type how many tweets you want to scrape.

- Type `0` to scrape every archived tweet URL the script finds.
- Type a smaller number, like `25`, if you only want to test the script first.

Recommended first test:

```text
25
```

Recommended full scrape:

```text
0
```

### Max timeout in seconds

This is how long the script waits for each Internet Archive request before
giving up and moving on.

Recommended value:

```text
10
```

For slow Internet Archive days, try:

```text
30
```

## Example Run

```text
Twitter handle: uwu_underground
Output CSV filename [uwu_underground_tweets.csv]:
Folder where tweet images should be saved [uwu_underground_images]:
Delay in seconds [0.5]:
Max-tweets (0 means all tweets) [0]: 25
Max timeout in seconds [10.0]:
```

In this example, blank answers use the default value shown in brackets.

## Non-Interactive Usage

Advanced users can provide everything in one command.

Windows:

```powershell
py twitter_archive_scraper.py --handle uwu_underground --output-csv uwu_underground_tweets.csv --image-folder uwu_underground_images --delay 0.5 --max-tweets 0 --timeout 10
```

macOS and Linux:

```bash
python3 twitter_archive_scraper.py --handle uwu_underground --output-csv uwu_underground_tweets.csv --image-folder uwu_underground_images --delay 0.5 --max-tweets 0 --timeout 10
```

## Output

The CSV has these columns:

1. Date of the original Tweet
2. The text of the tweet
3. Internet archive URL

Images are written to the image folder you chose.

## Important Notes

- Large accounts can take a long time.
- The Internet Archive can be slow.
- Some archived tweets may not have enough preserved data to extract text.
- Some images may be listed in a tweet but may not have been preserved by the
  Internet Archive.
- If the script appears to pause, it may simply be waiting for the Internet
  Archive.
- Press `Ctrl + C` to stop the script early.

## Troubleshooting

### Windows says `py` is not recognized

Python may not be installed, or it may not have been added to PATH.

Try:

```powershell
python --version
```

If that does not work, reinstall Python and make sure to check:

```text
Add python.exe to PATH
```

### macOS or Linux says `python3` is not found

Python is not installed or not available in your terminal.

Install Python using the instructions above, then close and reopen the terminal.

### The script found URLs but skipped some tweets

This can happen when the Internet Archive has a URL listed but the preserved
payload is missing, incomplete, blocked, or temporarily unavailable.

Try again later with a higher timeout:

```text
60
```

Also try a larger delay:

```text
5
```

### The CSV opens strangely in Excel

Open Excel first, then import the CSV:

1. Open Excel.
2. Click `Data`.
3. Click `From Text/CSV`.
4. Select the CSV file the scraper created.
5. Choose UTF-8 if Excel asks about encoding.

## How It Works

The tool queries the Internet Archive CDX API for both:

- `https://twitter.com/<handle>/status*`
- `https://x.com/<handle>/status*`

It asks CDX for capture timestamps and original URLs without filtering by HTTP
status code. That matches the broad CDX URL lists shown by the Internet Archive
and avoids dropping archived tweet URLs that were preserved as redirects,
revisits, or other non-200 records. The scraper then deduplicates by tweet
status ID, fetches the raw archived payload for each tweet, extracts tweet
metadata from either HTML or Twitter/X JSON captures, and downloads likely
attached media from `pbs.twimg.com/media/` through Wayback.

Internet Archive can be slow or rate-limited, so the scraper uses request
timeouts, retries on transient failures, and a user-controlled delay between
tweet fetches.

## Official Python Help

- [Download Python](https://www.python.org/downloads/)
- [Using Python on Windows](https://docs.python.org/3/using/windows.html)
- [Using Python on macOS](https://docs.python.org/3/using/mac.html)
- [Using Python on Unix platforms](https://docs.python.org/3/using/unix.html)
