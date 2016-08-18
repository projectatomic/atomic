% Brent Baude
% August 2016 

# Atomic Scan JSON specification
 
When creating a custom scanner plug-in, the JSON needs to be formatted in a specific
way for Atomic to be able to output a summary for the user.

Each JSON output file should have the following basic key and value pairs:

```
{
  "Scanner": "",  # String name
  "Time": "", # Time stamp
  "Scan Type": ""   # String name
  "Finished Time": "", # Time stamp
  "UUID": "", 
  "Successful": "" # String bool (true/false)

  ...
```
At this level in the JSON, you can also inject custom information within a "Custom" key.  For example:

```
  "Custom": {
     "scanner_url": "http://foobar"
     ...
     }
```

Atomic scan will then look for one of two additional keys: Vulnerabilities or Results.  If that key
is present, it will then iterate recursively through the tree. An actual example from the openscap
scanner looks like the following:

```
{
  "Scanner": "openscap",
  "Time": "2016-08-09T13:50:47",
  "CVE Feed Last Updated": "2016-05-31T03:16:12",
  "Scan Type": "CVE",
  "Finished Time": "2016-08-09T13:50:49",
  "UUID": "/scanin/53f20e902da704bc7efebf0c24e03ce1233cd364c5987ef895c9827fbc340474",
  "Successful": "true"
  "Vulnerabilities": [
    {
      "Title": "RHSA-2016:1025: pcre security update (Important)",
      "Severity": "Important",
      "Description": "PCRE is a Perl-compatible regular expression library.\n\nSecurity Fix(es):\n\n* Multiple flaws were found in the way PCRE handled malformed regular expressions. An attacker able to make an application using PCRE process a specially crafted regular expression could use these flaws to cause the application to crash or, possibly, execute arbitrary code. (CVE-2015-8385, CVE-2016-3191, CVE-2015-2328, CVE-2015-3217, CVE-2015-5073, CVE-2015-8388, CVE-2015-8391, CVE-2015-8386)",
      "Custom": {

```

If you do not want to output anything to the user, then simply do not use the Results or Vulnerabilities
keys.

In the case that you want some simple output for the user, you can use the Custom key at the top
top level (as shown above).  This will be shown to the user.  A good example would be if your 
scanner pushes the results to a web site, you could list that.

