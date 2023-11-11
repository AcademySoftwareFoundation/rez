# Rez TSC Meeting Notes - 2023-07-20

:movie_camera::scroll: Recording: https://zoom.us/rec/share/Culqby6gmanuJdxIlOOdwN6ajT0EC66-4R33N-WkV6gZZpPcbfMtOlliDKE_cj7r.DLfjjVpSLMapRrdl

## Attendance

* Host: Stephen Mackenzie
* Secretary: Stephen Mackenzie
* TSC Attendees:
  * [ ] Allan Johns - NVIDIA (resigned)
  * [x] Brendan Abel - Walt-Disney Imagineering
  * [x] Jean-Christophe Morin - Freelance
  * [x] Stephen Mackenzie - NVIDIA
  * [x] Thorsten Kaufmann - Mackevision / Accenture
* Other Attendees:
  * [x] John Mertic - ASWF
  * [x] Rob Bridger-Woods
  * [x] Blazej Floch
  * [x] Jeff Bradley - Dreamworks
  * [x] Joel Pollack
  * [x] Thorsten Kaufmann
  * [x] Matthew Low
  * [x] Jonas Avrin
  * [x] Jason Scott
  * [x] Erwan Leroy
  * [x] Ibrahim Sani Kache
  * [x] Dhruv Govil
  * [x] Paolo Audiberti

## Agenda
* Agenda Issue: https://github.com/AcademySoftwareFoundation/rez/issues/1512
* [x] TSC Items
  * [x] Some big news
  * [x] Virtual Town Hall style/announce/prep.
* [x] Dreamworks!
  * [x] Short (approximately 10-min) demo produced out of interest in their OpenMoonray release which included package.py's and some interesting usage details.
* [ ] Windows Shell PR
  * [ ] Some followups and urgency
* [ ] Hopefully a release soon

## Short Version / Decisions / Action Items / Important Links

* Decisions:
  * Jean-Christophe Morin & Stephen Mackenzie will co-chair for rez
  * Engage with LFX to help shutter googlegroup
  * Double check that rez-talk slack is gone
* Discussions:
  * Virtual Town Hall prep
  * Dreamworks Demo
* Actions Items:
  * Update repo in response to Allan resignation
  * Try to check for anything that is still connected to Allan
    * Slack
    * google-group
    * codeowners
    * repo settings
    * any CI related things

## Details

### TSC Items

#### Allan resigns & Chair

* (SM):
  * Allan has tendered his Chair & TSC resignation
  * Won't have time for any significant project effort in the near-term
  * Might come back in the future, but we shouldn't count on that
  * We'll need to go through the process of selecting a new chair
  * Community has relied a lot on Allan's maintainership so it's going to be important for the rest of us to step up and fill his shoes to a degree.
  * John, anything you want to jump in with?
* (JM):
  * Echo Stephens statements, hard being a lone wolf maintainer for so long.
  * Him bringing the project to the ASWF showed he was looking down the road and making sure rez would be in good hands
  * Can be hard for a maintainer to see that far down the road but it's clear he thought so much about this community and industry.
  * Two halves of things to take care of,
    * One is just an inventory the project should do to make sure there are no other accounts or resources that Allan is directly attached to that others don't have access to.
    * Two is moving forward for a new chairperson.
    * Really it's up to this group to decide what that looks like.
    * Doesn't even have to long, you can just try it for a couple months and pass it along if you like.
* (SM):
  * I'll jump in one thing about the accounts stuff.
  * Vast majority of that is handled, as part of the incubation process
  * Only thing we probably need to look at is the legacy google group that maybe the LF can help us archive or preserve in some way.
* (JM):
  * Yeah, we'll have to figure that one out
* (TK):
  * I'm not currently 100% sure we completely dismantled the old slack. We did take a backup and remove access, but we should double-check.
* (SM):
  * Some homework for us TSC people to figure out.
  * As for chairperson stuff, I figured I would leave it to each person to say they are too busy or whatever, and from there figure out what the best option is.
  * Spoke with JCM so even though he's not here, I know where his opinion is, but I figured I'd let Thorsten and Brenden speaks up if they want to.
* (TK):
  * Not really an option for me due to time constraints
  * Taking a new role in the company currently and little under load
  * Definitely still interested in contributing however, but for the time being I just can't put as much time into the project as will be needed
* (BA):
  * Yeah, pretty much same as Thorsten.
* (SM):
  * So I did speak to JCM and he and I basically said, we were guessing that would be the case,
  * And while neither of us has all the time required befitting a chair position, we seem similarly active and present in the ASWF meetings,
  * So between the two of us, we might make one functional unit, so splitting the position might be an option for us if everyone is comfortable with it.
  * Of course I'm happy to let him show up later hopefully if he can, but that was kind of where we were standing.
  * Any issue with that?
* (JM):
  * Yeah, however you all want, up to you all and if the TSC is good with that approach, we can make that happen.
* (SM):
  * One thing we might want to take care of sooner than later would be backfilling Allan's spot.
  * We should discuss in more detail.
  * If anyone is interested in stepping up, they should let us know.
  * Will put out an announce more generally in the slack later on that, including what that amounts to.
  * Prcoedurally, we should just vote on this?
    * Vote occurred, TK & BA vote yes
* (TK):
  * Want to say thanks for stepping in even if you share it, it's very appreciated, you two have been filling in a lot.
* (JM):
  * We'll make sure you're on the tac invites and things of that nature.

#### Virtual Town Hall prep

* (SM):
  * I did sign up rez to do a virtual town hall and not a BoF.
  * It's next week, Wednesday
  * I will be assembling an announcement with all the details such as here's what it will be, here's how to register, etc.
  * rez being a little different, we rely more on community discussion and feedback so beyond the usual intros and such, we'll be focusing on community discussions and voting on things to get the pulse of the community.
  * Looking to use a pollev.com style system where people can anonymously submit whatever they want and upvote.
  * That'll be an hour long next week.
  * I'll be doing most of the announcement and prep work stuff.

### Dreamworks

* (SM):
  * Next item is a bit more exciting
  * Several people got interested by the openmoonray rez package and some of what it had inside it, so dreamworks graciously agreed to talk about some of what they do, how they do it, etc.
* (JB):
  * I have some slides, manage our team, and we have a few people here to answer questions and so forth.
  * Presentation: [Slides](presentation.pdf).
  * (Q&A with Joel Pollock, Matthew Low, Ibrahim Sani Kache)

### Ending remarks
* (SM):
  * Will be sure to post the recording out.
* (JCM):
  * Crafty apes will present some work next week as well, just to not forget about it.
* (SM):
  * Mike Owen in slack asking for feedback on Deadline integration stuff, please check it out if it pertains to you.
  * Thanks so much to Jeff and the rest of the Dreamworks team