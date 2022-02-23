
This is a temp document for keeping track of ASWF adoption progress.
Copied and modified from
https://github.com/AcademySoftwareFoundation/asfw-sample-project/blob/main/tsc/project_intake.md

# Internal Checklist

Misc stuff not covered in the ASWF list

- [ ] Move from master to main branch [#1203](/../../issues/1203)
- [ ] Remove hardcoded references to `nerdvegas` where possible (some of these won't make sense to do until after gh migration) [#1205](/../../issues/1205)
  - TODO: inline links in comments (will need a script to batch convert)
  - TODO: README.md
- [ ] Update Github slack integration [#1204](/../../issues/1204)

# ASWF Onboarding Checklist
- Existing Project Governance
  - [X] A [LICENSE](../LICENSE) file in every code repository, with the license chosen an OSI-approved license.
  - [X] Any third-party components/dependencies included are listed along with thier licenses ( [THIRD_PARTY.md](../THIRD_PARTY.md) ) [#1227](/../../issues/1227)
  - [ ] A [README.md](../README.md) file welcoming new community members to the project and explaining why the project is useful and how to get started.
    - (exists but requires review)
  - [ ] A [CONTRIBUTING.md](../CONTRIBUTING.md) file explaining to other developers and your community of users how to contribute to the project. The file should explain what types of contributions are needed and how the process works, along with how to disclose security issues responsibly ( may also point to a [SECURITY.md](../SECURITY.md) file ).
    - (exists but requires review)
  - [X] A [CODEOWNERS](../CODEOWNERS) or [COMMITTERS](../COMMITERS.csv) file to define individuals or teams that are responsible for code in a repository; document current project owners and current and emeritus committers. [#1226](/../../issues/1226)
  - [X] A [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) file that sets the ground rules for participants’ behavior associated and helps to facilitate a friendly, welcoming environment. By default, projects should leverage the Linux Foundation Code of Conduct unless an alternate Code of Conduct was previously approved. [#1227](/../../issues/1227)
  - [ ] A [RELEASE.md](process/release.md) file that provides documentation on the release methodology, cadence, criteria, etc.
    - (exists but requires review)
  - [ ] A [GOVERNANCE.md](../GOVERNANCE.md) file that documents the project’s technical governance. [#1229](/../../issues/1229)
  - [ ] A [SUPPORT.md](../SUPPORT.md) file to let users and developers know about ways to get help with your project. [#1230](/../../issues/1230)
- Infrastructure/Assets
  - [ ] License scan completed and no issues found
  - [ ] Code repository imported to ASWF GitHub organization or ownership of current GitHub organization given to `thelinuxfoundation` user
    - [ ] Developer Certificate of Origin past commit signoff done and DCO Probot enabled.
  - [X] Issue/feature tracker established (JIRA, GitHub issues)
  - [X] Mailing lists ( one of )
    - [ ] Setup new lists ( -discuss@ and -tsc@ ) on [ASWF groups.io](https://lists.aswf.io) ( create [issue on foundation repo](https://github.com/AcademySoftwareFoundation/foundation/issues/new) to setup )
    - [X] Move to [ASWF groups.io](https://lists.aswf.io) ( create [issue on foundation repo](https://github.com/AcademySoftwareFoundation/foundation/issues/new) to transfer )
  - [X] Slack ( create [issue on foundation repo](https://github.com/AcademySoftwareFoundation/foundation/issues/new) to setup project channel on [ASWF Slack](https://slack.aswf.io)
  - [ ] Website
  - [X] CI/build environment
  - [ ] Trademarks/mark ownership rights ( complete 'LF Projects - Form of Trademark and Account Assignment' - create [issue on foundation repo](https://github.com/AcademySoftwareFoundation/foundation/issues/new) - only needed if project using existing name )
  - [ ] Domain name ( create [issue with the LF IT staff](https://jira.linuxfoundation.org/plugins/servlet/theme/portal/2/group/19) to setup/transfer )
  - [ ] Zoom account access ( create [issue on foundation repo](https://github.com/AcademySoftwareFoundation/foundation/issues/new) to get access to credentials )
  - [ ] Social media accounts or other project accounts ( create [issue on foundation repo](https://github.com/AcademySoftwareFoundation/foundation/issues/new) to transfer )
    - [ ] Logo(s)   ( create [issue on artwork repo](https://github.com/AcademySoftwareFoundation/artwork/issues/new) to add in SVG and PNG format and color/black/white )
      - (in progress)
- New Project Goverance
  - [ ] TSC members identified
  - [ ] First TSC meeting held
  - [ ] TSC meeting cadence set and added to project calendar
  - [ ] CLA Approved ( if used ) ( [CCLA](ccla.md) and [ICLA](icla.md) )
  - Project charter ( [charter.md](charter.md) )
    - [ ] Approved by TSC
    - [ ] Filed ( create pull request against [foundation repo](https://github.com/AcademySoftwareFoundation/foundation) )
  - [ ] [Core Infrastructure Initiative Best Practices Badge](https://bestpractices.coreinfrastructure.org/) achieved as the 'Passing' level.
  - [ ] TAC representative appointed
- Outreach
  - [X] New project annoucement done ( create [issue on foundation repo](https://github.com/AcademySoftwareFoundation/foundation/issues/new) to trigger )
  - [ ] Project added to ASWF website and ASWF landscape
- Adopted Stage graduation requirements
  - [ ] CII Badge   achieved
  - [ ] Demonstrate a substantial ongoing flow of commits and merged contributions, authored by a healthy number of diverse contributors*.
  - [ ] Demonstrable roadmap progress.
  - [ ] A healthy number of public adopters that are identified within the project ( using an ADOPTERS file or showcased on the project’s website ).
  - [ ] [Core Infrastructure Initiative Best Practices Badge](https://bestpractices.coreinfrastructure.org/) achieved as the 'Passing' level.
  - [ ] Submit intent to graduate to TAC for consideration during future meeting, outlining achievement of the [Adopted stage requirements](https://tac.aswf.io/process/lifecycle.html#adopted-stage)
  - [ ] 2/3 supermajority vote of the TAC
  - [ ] Affirmative majority vote of the Governing Board
