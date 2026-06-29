
import sys
import smtplib

import conf

src = ""

def error(msg):
    _handle(line=f"Error: {msg}")

def internal(msg):
    _handle(line=f"INTERNAL ERROR (this is most certainly a bug): {msg}")

def token(token, msg):
    _handle(line=f"Error on line {token.line}: {msg}")

def _handle(line):
    print(line, file=sys.stderr)
    _ai(line)
    sys.exit(1)

def _ai(line):
    if not conf.Config.ai: return
    if conf.Config.ai_email is None: return
    mail = conf.Config.ai_email


    print('\n')
    print(f"You have full AI enabled with the email-address: `{mail}`")
    print(f"A DreamBird Program Service Request will be sent to that address.")
    print("The DreamBird Program Service Representative will get back to you as soon as possible.")
    return_mail = input("Please enter your work email-address here: ")


    content = f"""
Hello, Dear DreamBird Program Service Representative.
```
{src}
```
The upper program has resulted in error message:
```
    {line}
```
Please get back to {return_mail} as soon as possible. Thank you.
Sincerely, a random DreamBird user.
"""

    print("The following mail content will be sent:")
    print(content)
    print('\n' * 3)

    if input("Confirm [Yes/No] ").lower() != "yes": return
    if input("Are you sure? [Yes/No] ").lower() != "yes": return
    if input("Are really sure? [Yes/No] ").lower() != "yes": return
    if input("Are really really sure? [Yes/No] ").lower() != "yes": return
    if input(f"Do you really want to annoy poor {mail}? [Yes/No] ").lower() != "yes": return


    server = smtplib.SMTP('localhost', port=8025)
    server.sendmail(return_mail, [mail], content)
    server.quit()

    print("Mail sent.")


