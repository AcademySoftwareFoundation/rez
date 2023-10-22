# Rez TSC Meeting Notes - 2023-08-17

:movie_camera::scroll: Recording: https://zoom.us/rec/share/2OLhyMTtN6ybQaodW1CUMPCvCRLGUNxsUlb3WcqBCCwlAWV3ELw8xjf53WzkVx-a.nRR2z27w-uJ1rJ5B

## Attendance

* Host: Jean-Christophe Morin
* Secretary: Jean-Christophe Morin
* TSC Attendees:
  * [x] Brendan Abel - Walt-Disney Imagineering
  * [x] Jean-Christophe Morin - Freelance
  * [x] Stephen Mackenzie - NVIDIA
  * [x] Thorsten Kaufmann - Mackevision / Accenture
* Other Attendees:
  * Deke Kincaid (Digital Domain)
  * Dhruv Govil (Apple)
  * Erwan Leroy (Carfty Apes)
  * Ibrahim Sani Kache (Dreamworks)
  * Jason Scott (Pitch Black)
  * Jeff Bradley (Dreamworks)
  * Jonas Avrin
  * John Riddle (Crafty Apes)
  * Junko V. Igarashi (Crafty Apes)

## Agenda
* Agenda Issue: https://github.com/AcademySoftwareFoundation/rez/issues/1513
* ASWF:
    * [x] Take ownership of https://rez.readthedocs.io [#1517](https://github.com/AcademySoftwareFoundation/rez/issues/1517)
    * [x] TSC chair transition after Allan stepped down [#1519](https://github.com/AcademySoftwareFoundation/rez/issues/1519)
* [x] @herronelou presentation on the usage of rez at https://www.craftyapes.com/.
* [x] Named Variants proposal: Named Variants [#1503](https://github.com/AcademySoftwareFoundation/rez/discussions/1503)

## Short Version / Decisions / Action Items / Important Links

* Action Items:
  * @AcademySoftwareFoundation/rez-tsc: Find a plan to unblock [#1503](https://github.com/AcademySoftwareFoundation/rez/discussions/1503).

## Details

### ASWF

#### Take ownership of https://rez.readthedocs.io

https://github.com/AcademySoftwareFoundation/rez/issues/1517

* JC:
    * We discovered that https://rez.readthedocs.io was pointing at the source of an old fork of rez.
    * Contacted the owner and he gave us admin access.
    * We now have the ability to update the documentation.
    * The current page is our own. We pushed an update using tip of the main branch.

#### TSC chair transition after Allan stepped down

https://github.com/AcademySoftwareFoundation/rez/issues/1519

* JC:
    * Mosty administrative tasks. Should be done now.
    * See the issue for more details.

## Crafty Apes presentation

* Erwan:
    * Working at https://www.craftyapes.com/ as the Global Head of 2D.
    * Want to present what we did at Crafty Apes and how we implemented rez in our pipeline.
* Presentation: [Slides](presentation.pdf).
* Q&A: See the recording (attached at the top of this page).
* Thanks a lot for this great presentation!

## Named Variants proposal

https://github.com/AcademySoftwareFoundation/rez/discussions/1503

* Dhruv:
    * I made this proposal.
    * What would the next steps be?
    * The biggest contention point is how to store named variants in a way
      that preserves the order and python 2.7 support.
    * We could use a standard dict, but that won't isn't compatible with Python 2.7.
    * And it would also only be compatible with 3.7+.
* Stephen: We could use this as an opportunity to drop support for Python 2.7.
* Jeff: As a studio that still supports Python 2.7. So we'll stick to the older rez version for a while until we can drop 2.7.
* JC: It's that it's always an option. Our users are not forced to upgrade to newer version of rez. And rez is failrly stable, so they can stay on an older version if they want to still use Python 2.7.
* Jason: Agree that studios can just pick an older version of rez if they want.
* Stephen: Studios can also install multiple versions of rez in parallel.
* Erwan: When they do so, they'll have to be carefull to not release packages that use features
  that older versions of rez won't know how to deal with.
* JC: We'll need to solve that. THough, we have added new package definition fields in the past and we've never heard of failrues due to that.
* Brendan: rez will ignore attributes it doesn't know. But we still need to find a solution to
  evolve the package definiton format.
* Dhruv: What are the next steps?
* JC: We should revive the discussion on GH. And the TSC will have to decide what to do to move things forward.
