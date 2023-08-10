# dashboard-web-server
This is the web server that acts at a backend for `tech-consulting-dashboard` and automates many consulting tasks

## Features 
* [TeamDynamix WebAPI](https://teamdynamix.umich.edu/TDWebApi/)
  * Check out assets requested in a loaner ticket with robust error handling!

## Planned Features
* [TeamDynamix WebAPI](https://teamdynamix.umich.edu/TDWebApi/)
  * Check in assets that were on loan
* Warranty Check APIs
  * [Apple](https://checkcoverage.apple.com/) (needs investigating)  
  * [HP](https://support.hp.com/us-en/check-warranty) (can implement)
  * [Dell](https://github.com/umich-tech-consulting/warranty-check/blob/main/docs/Dell%20Warranty%20API%20Spec%20-%20Rev%202_5.pdf) (implementing)
  * [Lenovo](https://pcsupport.lenovo.com/us/en/warranty-lookup#/) (can implement)
  * [Safeware](https://www.safeware.com/lookup/CoverageDetail/ContactSafeware) (needs investigating)

## Technical Details
The web server is written in Python 3.11.3 using Quart. It communicates with TeamDynamix using the [`tdxapi`](https://github.com/umich-tech-consulting/tdxapi)
