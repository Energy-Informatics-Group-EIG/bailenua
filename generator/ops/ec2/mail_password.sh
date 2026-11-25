#!/bin/sh
# Prints the Gmail app password for msmtp's passwordeval. PARSES the env file
# (never sources it: the value contains spaces) and prints nothing else.
# Spaces are removed: Google shows app passwords in groups of four, and SMTP
# AUTH takes the 16 characters without them.
sed -n 's/^[[:space:]]*\(export[[:space:]]\{1,\}\)\{0,1\}GMAIL_APP_PASSWORD=//p' /home/ubuntu/.mail_baile_nua.env 2>/dev/null \
  | head -n 1 | sed -e "s/^[\"']//" -e "s/[\"'][[:space:]]*\$//" | tr -d ' \t\r\n'
