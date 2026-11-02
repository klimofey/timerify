# Voice

This page shows what you can say to Assist about a timer, and how to set it up.

## The built-in agent and LLM agents

Assist is Home Assistant's voice assistant. Timerify answers to it in English and Russian. Assist hands what you say to a conversation agent. There are two kinds.

- **The built-in agent** is Home Assistant's own agent. It understands a fixed set of sentences. You give it Timerify's sentences once, as described in [Set up the sentences for the built-in agent](#set-up-the-sentences-for-the-built-in-agent).
- **An LLM agent** is an agent that uses an AI model. It is given tools and chooses its own words. See [Tools for LLM agents](#tools-for-llm-agents).

Add a timer to each device first. See [Timers](timers.md#add-a-timer-to-a-device).

Voice goes the way [actions](services.md) go. A timer changes only through its own countdown. So "turn on the boiler for 10 minutes", said aloud, does the same as the [**Run** action](services.md#run). Both are refused for the same reasons.

## What you can say

A sentence names a device that has a timer. The device must be [exposed to Assist](#let-assist-control-your-devices). Say the name as Home Assistant shows it, or one of its aliases. The examples say "the boiler".

Each sentence has more wordings than the table shows. In English, "the" is optional, and the verbs have synonyms. A duration is hours, minutes or both. "Half an hour" and "an hour and a half" work too. The complete sentences are the files in the folder [`sentences/<language>/`](../../custom_components/timerify/sentences/) of Timerify.

| What | English | Russian, transliterated |
| --- | --- | --- |
| How long is left | how much time is left on the boiler | skol'ko vremeni ostalos' u taymera Boiler |
| Run for a time | turn on the boiler for 10 minutes | vklyuchi Boiler na 10 minut |
| Set the countdown | set the boiler timer to 90 minutes | postav' taymer Boiler na 90 minut |
| Run with settings | turn on the AC for an hour, cooling, 24 degrees | vklyuchi AC na chas v rezhime okhlazhdeniya 24 gradusa |
| Run at a level | turn on the lamp for 20 minutes at 40 percent | vklyuchi Lamp na 20 minut na 40 protsentov |
| Add time | add 15 minutes to the boiler | dobav' 15 minut k taymeru Boiler |
| Stop | stop the boiler timer | ostanovi taymer Boiler |
| Turn on or off by name | turn on the boiler, turn off the boiler | vklyuchi Boiler, vyklyuchi Boiler |
| Turn on later | turn on the boiler in 15 minutes for an hour | vklyuchi Boiler cherez 15 minut na chas |
| Turn off later | turn off the boiler in 20 minutes | vyklyuchi Boiler cherez 20 minut |
| Turn on at a time | turn on the boiler at 7:30 | vklyuchi Boiler v 7:30 |
| Turn off at a time | turn off the boiler at 7:30 | vyklyuchi Boiler v 7:30 |
| What is planned | what is planned for the boiler | chto zaplanirovano u taymera Boiler |
| Cancel what is planned | cancel all planned commands for the boiler | otmeni vse zaplanirovannye komandy u taymera Boiler |
| Cancel the next one | cancel the next planned command for the boiler | otmeni blizhayshuyu zaplanirovannuyu komandu u taymera Boiler |
| Switch the schedule | turn off the boiler schedule, turn on the boiler schedule | vyklyuchi raspisanie taymera Boiler, vklyuchi raspisanie taymera Boiler |
| Switch one interval | turn off the Morning schedule of the boiler | vyklyuchi raspisanie Utro taymera Boiler |

The Russian column is transliterated because this page is in English. The real sentences are in the Russian pages and in the sentence files. A device keeps the name you gave it, here Boiler, AC and Lamp. A Russian name is not declined. So where a sentence would decline it, the Russian sentences put it after a noun, such as "taymera Boiler". The Russian answers start with the name and a colon.

### What each sentence does

**How long is left**

- It tells the time left and when the device turns off. It can also say that the device is off, is unavailable, or is on without a timer.
- It says "unavailable" when the device does not answer (unavailable or unknown) and no timer wants it on.

**Run for a time**

- It does the same as setting **Run for**. The countdown is that long, from one minute to 24 hours. It replaces a countdown that runs.
- You can say a longer time, as far as a week, such as "for 30 hours". Write minutes beyond a day in digits, such as "for 2000 minutes". The sentence is understood and refused with the limit, and nothing is turned on. A count of hours or minutes beyond a week is not understood at all.
- If a number of minutes follows the hours, with or without "and", it adds to them. "For 1 hour 30" and "for 1 hour and 30" are both 90 minutes. You can leave out the word "minutes".
- The exception is turning on a thermostat or a water heater for a time. There "for 1 hour 30" means one hour at 30 degrees. Say "and" or "minutes" for the minutes: "for 1 hour and 30" is 90 minutes.
- A thermostat, a water heater, a light, a fan or a humidifier takes its settings in the same sentence, in any order:
  - the HVAC mode ("cooling", "heating", "auto");
  - a temperature ("24 degrees", "at 22.5", or "120 degrees" for a water heater in Fahrenheit). Any number up to 250 works, in digits or words. The device then accepts or refuses it by its own range;
  - a percentage ("at 40 percent");
  - a mode of the device ("eco", "high").
- A device is understood to take a setting only if it has that setting. The request is checked against the device as the **Run** action checks it. What the device cannot do is refused, by voice and by an LLM agent alike.

**Add time**

- It extends a running countdown. If none runs, it turns the device on for that long.
- A countdown never ends more than a day ahead. Adding 30 hours, or any count up to a week, gives a day. The answer says when it ends.

**Stop**

- It sets the countdown to zero and turns the device off.

**Turn on or off by name**

- These are the bare "turn on the boiler" and "turn off the boiler". For a device that has a timer, they are Timerify's commands, not Home Assistant's.
- Turning on a device that is off follows the timer's mode. The [Modes](timers.md#modes) section explains both. In **Strict** mode a device runs only while a countdown does, so it runs for the default duration. In **Loose** mode it may also run without a countdown, so it is on without one.
- Turning on a device that is running leaves it as it is. Its countdown keeps its end, whoever set it. The answer says how long is left.
- Turning off stops the countdown.
- A device that is unavailable keeps what you asked for. It is switched when it is back.
- Wordings with an area, a floor or a kind of device stay with Home Assistant. An example is "turn off the lights in the kitchen". So does every device without a timer.

**Turn on later and turn off later**

- These are Home Assistant's own delayed commands. Timerify takes them over for the devices that have a timer.
- It takes over every shape that Home Assistant has for them, in both languages. The delay can come before or after the command. It is in hours, minutes and seconds. English takes "in" or "after". English also takes the form with the name last, "in 15 minutes boiler".
- A command to turn on is kept as a [pending command](pending-commands.md). It survives a restart, shows on the **Next command** sensor and can be cancelled.
- A command to turn on can say how long the device then runs, and its settings. An example is "turn on the AC in 15 minutes for an hour, cooling, 24 degrees".
- A command to turn off sets the countdown of a running device to end then. It replaces the end, whether the device had a countdown or not. For a device that is off, nothing changes, and the answer says so.
- A delay is at most a week for a command to turn on, and a day for a command to turn off. A timer keeps at most 20 pending commands. A command beyond these limits is refused with a message.
- You can say a delay as long as a week, as for "Run for a time". That is up to 168 hours, or up to 10080 minutes. Write minutes beyond a day in digits. Seconds go up to 100. A delay within a week but beyond the limit of the command is understood and refused, and the answer names the limit. A count of hours or minutes beyond a week is not understood at all.
- You can also say a delay in days or weeks, such as "turn on the boiler in 2 days" or "turn on the boiler in 2 weeks". In Russian that is "vklyuchi Boiler cherez 2 dnya". Days go up to 365, and weeks up to 52. You cannot join days or weeks with hours or minutes.
- "In a day", "in half a day" and "in a week" work too. In Russian they are "cherez den'", "cherez poldnya" and "cherez nedelyu".
- In English, you can end a delay with "from now", "from today" or "later". It works with days, weeks and these words. Examples are "turn on the boiler 2 days from now" and "turn on the boiler a week later". You can say it before the command too: "a week from now turn on the boiler".
- The limits above hold for days and weeks. So "turn off the boiler in 2 days" is refused, because a countdown runs for a day at most. "Turn on the boiler in 2 weeks" is refused too. The answer names the limit. More than 365 days or 52 weeks is not understood at all.
- Devices without a timer keep Home Assistant's delayed commands untouched.

**Turn on or off at a time**

- You can name a time of day instead of a delay, such as "turn on the boiler at 7:30" or "turn off the boiler at 23:00". Home Assistant has no such sentences. Timerify adds them for the devices that have a timer.
- The time can come after the command or before it: "at 7:30 turn on the boiler".
- You can add a day: "today", "tomorrow" or "the day after tomorrow". Say it before the time or after it: "tomorrow at 7" or "at 7 tomorrow".
- You can say the time as "7:30", "7.30" or "7 30", or in words, such as "seven thirty". "7 o'clock", "noon" and "midnight" work too.
- "Am" and "pm" tell the morning from the evening: "at 7 am", "at 7:30 p.m.". So do "in the morning", "in the afternoon", "in the evening" and "at night", as in "at 7 in the evening". "At 2 at night" is 02:00, and "at 11 at night" is 23:00.
- You can also put the part of the day before the hour, after a day or after "in the". Examples are "tomorrow morning at 7" and "in the evening at 7:30".
- In Russian the words "utra" (morning), "dnya" and "vechera" (afternoon and evening) and "nochi" (night) do the same. "V 2 nochi" is 02:00, and "v 11 nochi" is 23:00.
- An hour from 1 to 12 without any of these is the nearer of its two times ahead. "At 7" said at 18:00 means 19:00 today. Said at 06:00, it means 07:00 today. Said at 20:00, it means 07:00 tomorrow. Say "am", "pm" or "in the morning" to choose the other one.
- With a day word, the same rule works on that day. So "tomorrow at 7" is 07:00 tomorrow.
- The hour 0 and the hours 13 to 23 are on the 24-hour clock. "At 19" is 19:00, and "at 0:30" is 00:30.
- "At noon" and "at 12 pm" are 12:00. "At midnight" and "at 12 am" are 00:00. A bare "at 12" is the nearer of the two.
- With a day word, "midnight" is the one that ends that day. "Today at midnight" is tonight's 00:00, and "tomorrow at midnight" is the one after tomorrow. "Tomorrow at 12 am" and "tomorrow at 0:00" are the start of tomorrow.
- With a day word, the small hours said with "night" belong to the night that follows that day. That means "at night" or "night" with the hours 12 and 1 to 5. "Tomorrow night at 2" and "tomorrow at 2 at night" are 02:00 the day after tomorrow. "Tomorrow night at 12" is the same as "tomorrow at midnight". "Today at 2 at night" is the coming 02:00. Said before 06:00, it is the night in progress while that time is ahead: at 00:30 it is 02:00 today. "Tomorrow at 2 am" is 02:00 tomorrow, and "tomorrow night at 11" is 23:00 tomorrow.
- Without a day, a time is the next one: today if it is still ahead, tomorrow if it has passed. With the word "today", a time that has passed is refused, and the answer names it.
- A time that the change of the clock skips happens later by the length of the gap, as in [the schedules](schedules.md#clock-changes-and-time-zones). A time that it repeats happens twice. Timerify takes the first of the two that is still ahead.
- A command to turn on is kept as a [pending command](pending-commands.md), as it is for a delay. It can say how long the device then runs, and its settings: "turn on the AC at 7:30 for an hour, cooling, 24 degrees".
- A command to turn off sets the countdown of a running device to end then, as it does for a delay. The time is at most a day ahead. A later time is refused, and the answer names the limit.
- A thermostat or a water heater reads a bare number after its settings as a temperature. An example is "turn on the AC for an hour at 21". So after the settings, say the time with a colon or a space between hour and minutes: "at 7:30" or "at 7 30". Or use "o'clock", "am", "pm", "noon", "midnight" or a part of the day, such as "at 7 in the evening". A bare hour and a dotted time ("at 7.30") are not taken as a time there. Before the settings, every form works. Russian needs no such care, because its time starts with "v".

**What is planned**

- It lists the pending commands in the order they are due. For each it gives the time it runs at, and for how long.
- It does not say their settings.

**Cancel**

- It takes away all the commands (the default) or the next one. Saying "the next" again takes the one after.
- A cancelled command never runs.
- An id cannot be said. To cancel one particular command, use an LLM agent or the [**Cancel command** action](services.md#cancel-command).

**Switch the schedule**

- It switches every interval of the timer's schedule on or off, as the interval switches do. It has the same effects, on the same conditions. See [How a schedule and your own changes meet](schedules.md#how-a-schedule-and-your-own-changes-meet).
- Switching off while a window runs stops the timer only if the schedule is running it. That means the end of the countdown came from that interval, and nobody has changed the timer since. Otherwise the run is yours, and it stays. If another open window wants the device, that window takes the timer over instead.
- Switching on inside a window runs the device for the rest of the window. The exception is a timer that already ends later. An interval that is on already is left as it is. So a device that was turned off during its window stays off until the next one.
- In English, you can say "scheduling" instead of "schedule", and you can leave out "the" before it. Examples are "turn off scheduling for the boiler" and "turn off schedule for the boiler".
- To switch one interval, say its title, such as "the Morning schedule of the boiler". Give your intervals titles of your own. The title that Timerify makes, such as `06:30–07:15, Sun–Thu`, cannot be said to the built-in agent.
- A title that two intervals share switches both. A title that another timer has, and this one does not, is refused. The answer names the first five titles this timer has.

### How Assist answers

- The answers are in the language of the request. A regional language such as `en-GB` uses the sentences of its language. A language that Timerify has no texts for is answered in English.
- An answer says what the timer is set to do. A command may wait for an unavailable device, or a device may ignore it. The answer still says what you asked for. The log has the rest.
- The question about the time left is the exception when nothing is wanted on. Then it says what the device shows: off or unavailable.

### When Home Assistant answers instead

A few things work the way Home Assistant does, not the way Timerify does.

- "Turn it off" and "them", after a question or a command about a device, are answered by Home Assistant's own commands. They switch the device, and the timer follows. But the answer is Home Assistant's. A device that is unavailable is not switched. Timerify keeps nothing of what you asked.
- Suppose a sentence of Timerify's names something that is not a device with a timer. Home Assistant then answers "not aware of any device". An example is "what is planned for the fan".
- Home Assistant can take a wording that Timerify does not have for a plain turn on or turn off of the device. This happens when it mentions a device with a timer and has "turn on" or "turn off" in it. Examples are "turn off the boiler tonight" and "turn on the boiler next week". Home Assistant then switches the device at once. It does this in English only. Use the wordings above.
- Say two entities have the same name, and one of them has a timer. Then "turn off the boiler" and the other sentences above mean the one with the timer. Likewise, "turn off the boiler schedule" means the schedule of the timer called Boiler. This holds even when another exposed entity is called "Boiler schedule". That entity is reached by other wordings, and by the interface.

## Set up the sentences for the built-in agent

The built-in agent needs Timerify's sentences. There are two ways to give it them. Use **either** the Voice settings entry **or** a copy made by hand, never both.

### Use the Voice settings entry

This is the way to use, unless you have a reason not to.

1. Open **Settings > Devices & services > Helpers**. Choose **Create helper**, then **Timerify**. In the menu, choose **Voice settings**. There is one such entry, and the menu does not offer it again.
2. Turn on **Add voice sentences for the built-in agent**. It is on to begin with. Pick the **Languages**: English, Russian, or both. Timerify picks your house language if it has it, and English otherwise.

Timerify then writes the file `custom_sentences/<language>/timerify.yaml` in your configuration folder, for each language you picked. The file holds the names of your timers' devices. Timerify tells the built-in agent to read the sentences again.

A name is listed the way Home Assistant lists every entity: with its aliases. The file also holds the words for the HVAC modes that the devices have. It holds the modes of fans, humidifiers and the like too. Each of them is listed in two ways. One is the mode as the device names it, with a space for an underscore. The other is the word Home Assistant shows for it in the language of the file. The Russian file has the Russian words, whatever language your house is set to.

Some modes have no word in the language of the file. Home Assistant then shows the English one, and so does the file. A mode that Home Assistant has no word for at all is listed as the device names it. A word that is also the name of another mode is listed for that mode only, so it cannot start the wrong one. A word that two modes of different devices share is listed for one of them only. The other mode is then said by its own name.

A name, an interval title or a mode that has the Russian letter yo (the one with two dots) is listed twice. One value has yo and the other has ye. Speech recognition often writes ye where Russian prints yo. So either is understood, and the answer gives the name as the device has it.

Timerify writes the file again when any of these happens:

- A timer is added, removed or reloaded.
- A device is renamed or gets another alias.
- A schedule interval is added, deleted or renamed.

It writes the file only when its text changes.

- Timerify checks the file with the parser Home Assistant uses (hassil) before it writes it. It checks every sentence, every list and every name, which has to be matched as it is said. A file that Home Assistant cannot read would break Assist for the whole language. So when a check fails, Timerify leaves the old file as it is and logs an error.
- Timerify writes only where there is no file, or where the file is its own. Its own file has the first line `# Managed by Timerify. ...`. A `timerify.yaml` of yours at that path is left as it is. That language is not written, and the log says so once.
- The files are removed when you turn off the option, disable the entry, remove the entry, or stop picking a language. They stay when Home Assistant restarts or the entry reloads.
- The sentences need Timerify's handlers. **Remove the Voice settings entry, or turn off its option, before you uninstall Timerify.** A file that is left behind makes the built-in agent fail on every phrase of it that matches. That includes the delayed commands it took over from Home Assistant. It fails until you remove the file by hand.
- Names are listed when a timer is set up or its device changes. A device may change its own list of modes later, for example after a firmware update. That is picked up at the next change. So is a new friendly name of a device that is not in the entity registry.

### Copy the sentences by hand

If you do not want Timerify to write into `custom_sentences`, copy the sentences yourself and keep them current. Use **either** this **or** the entry above, never both. The entry logs a warning when it finds this copy. Two sets of sentences confuse the agent.

For each language you want (`en`, `ru`):

1. Make the folder `config/custom_sentences/<language>/timerify_manual/`.
2. Copy into it the files at the top of Timerify's folder `sentences/<language>/`. In your installation that is `custom_components/timerify/sentences/<language>/`. The files are `timerify.yaml` and `core_commands.yaml`, and only those. The folder `src/` beside them holds the sources they are generated from. Do not copy it. Home Assistant reads every folder below `custom_sentences/<language>/`.
3. Add a file of your own, `timerify_names.yaml`. It lists the devices. To say an interval by its title, it lists the titles too.

   ```yaml
   language: en
   lists:
     timerify_target:
       values:
         - in: "boiler"
           out: "Boiler"
           context:
             domain: switch
         - in: "AC"
           out: "AC"
           context:
             domain: climate
     timerify_interval:
       values:
         - in: "Morning"
           out: "Morning"
   ```

   - `in` is the name as it is said, with the punctuation that Home Assistant ignores removed. Say it has any of the characters `( ) [ ] { } < > | @`. Then put a backslash before each of them, and before every backslash in it. Home Assistant would otherwise read them as a sentence template. `out` is the name as Home Assistant shows it.
   - Give each name its `context: domain`, which is the part of the entity id before the dot. Settings are said only of a device that has them. A thermostat's HVAC mode and temperature need `climate`. A water heater's temperature needs `water_heater`. A name with no domain gets the sentences that fit every device, and nothing more.
   - `timerify_interval` is needed only to switch a schedule interval by its title. The whole schedule needs none.
   - To say a thermostat's fan mode, a fan's preset or a humidifier's mode, list the values under `timerify_mode` the same way. `in` is the mode as it is said, with a space for an underscore. `out` is the mode as the device names it. The words for the HVAC modes are in `timerify.yaml` already, for every mode. A mode that the device does not have is refused when it is said.
   - List the word Home Assistant shows for a mode as well, if you want to say it. Give it the same `out` as the mode. The entry does this for you, but a copy made by hand holds only what you write.
   - List a name with the Russian letter yo twice: once with yo and once with ye. Both values have the same `out`. Do the same for a title and a mode. Speech recognition often writes ye, and Home Assistant does not treat the two letters as one.
4. Restart Home Assistant, or call `conversation.reload`.

Do it again after every update of Timerify, because the sentences change between versions. Do it again after every rename of a device or an interval. A file that is not valid breaks Assist for the whole language. The entry above protects you from that, by checking before it writes. Check yours by reading the log after the reload.

## Let Assist control your devices

Assist can control only what is exposed to it. Home Assistant exposes new entities of some kinds by default. Among them are switches, lights, fans, climate entities, humidifiers and water heaters. It does not expose others, such as an input boolean or a group.

Open **Settings > Voice assistants > Expose**. Expose the devices of your timers that are not exposed yet. A device that is not exposed is refused ("Sorry, Boiler is not exposed"). An LLM agent is told only about the exposed ones.

Timerify's own entities are not exposed by default. They are **Run for**, the sensors and the interval switches. The switch of an interval is an entity of the configuration category, which Home Assistant leaves out.

## Tools for LLM agents

An LLM agent that uses the Assist API is offered these tools. This holds while a device with a timer is exposed to its assistant. The prompt names those devices. A tool takes the device's name and does what the sentence above does, through the same code. A refusal comes back as text, in the language of the request.

| Tool | What it does |
| --- | --- |
| `timerify__time_left` | Tells how long is left, and when the device turns off. Or that it is off, unavailable, or on without a timer. |
| `timerify__run` | Turns on for a number of hours and minutes, with settings. With neither, a device that is off runs for the usual time, and a device that is running keeps its countdown. |
| `timerify__add_time` | Adds hours and minutes to the countdown. |
| `timerify__stop` | Stops the timer and turns the device off. |
| `timerify__delayed_command` | Plans to turn on or off later. You give a delay in weeks, days, hours, minutes and seconds, or a date and time on the house's clock, never both. A turn-on can say how long it then runs, and its settings. It can be up to a week ahead. A turn-off can be up to a day ahead. |
| `timerify__list_commands` | Lists the planned commands, with the ids that cancel them. |
| `timerify__cancel_commands` | Cancels all the commands, the next one, or one by its id. |
| `timerify__set_schedule` | Switches the schedule on or off, or one interval by its title. |

If the interval is empty, the whole schedule is switched.

## What you cannot say

- **Taking time off**, such as "10 minutes less". Set the countdown to the new length instead.
- **Planning a command to turn off.** "Turn off in 20 minutes" sets the countdown instead. A pending command to turn off is made with the **Add command** action.
- **Cancelling one command by its id.** Only an LLM agent or the **Cancel command** action has the id.
- **An interval by the title it is made with.** Rename it first.
- **Two thermostats with different HVAC modes.** The words are the modes of all of them. So if you say a mode that only one of them has to the other, it is refused. The answer lists the modes that thermostat has.

---

[All pages](README.md) · [Back to the README](../../README.md)
