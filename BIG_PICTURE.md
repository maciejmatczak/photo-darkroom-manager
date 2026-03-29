# Big Picture

How does the photo darkroom manager fit into the big picture?

## Structure

### Drop off

Where all of the files from multiple sources are dropped off for further processing. Ingest input point.

```
/.../<DROP_OFF>/
	<DEVICE>/
		<files in any structure>
```

- input
	- phone: from Google Photos
	- camera: from SD card
- location: PC
- definitions
	- `DROP_OFF` - drop off directory
	- `DEVICE` - universe unique name, can have user prefix for team-like scenarios
- backup
	- remote: no
	- nas
		- Synology Drive - bare copy
		- snapshots?
- flow
	- review the files
	- recognize events
	- move files from one event into a Darkroom album
- operations
	- "tidy" - put files in year/month folders + PHOTOS/VIDEOS?
- transition
	- to Darkroom Album

### Darkroom

The place for edits and active work for photos culling end developing. After job is done, photos and videos are published.

```
/.../<DARKROOM>/
	<YEAR>/
		<ALBUM>/
			PUBLISH/
			<DEVICE>/
				PHOTOS/
				VIDEOS/
```

- input
	- moved files from Drop off into `DEVICE` folder
- location: PC
- definitions
	- `DARKROOM` - Darkroom directory
	- `ALBUM` - must include date and optional name
	- `PHOTOS/`, `VIDEOS/` - additional buckets as photos and videos are ingested differently
	- `PUBLISH/` - folder containing
- backup
	- remote: no
	- nas
		- Synology Drive - bare copy
		- snapshots?
- flow
	- tidy files
		- put files in PHOTOS/VIDEOS
			- this stage explicitly it should be done automatically when creating an album?
	- photos/video cull, development
	- if done, export to `PUBLISH/`
- operations
	- tidy - put files in PHOTOS/VIDEOS
	- publish - moves `/PUBLISH` file to the Showroom
	- archive - moves currently selected folder into Archive
		- supports high granularity of folder bases archivization, depending on cull and develop progress

### Showroom

The golden catalog of all of photos in videos in a known structure.

```
/.../<SHOWROOM>/
	<YEAR>/
		<ALBUM>/
```

- input
	- moved files from Darkroom `PUBLISH` into an `ALBUM`
- location: NAS
- definitions
	- `SHOWROOM` - Showroom directory
- backup
	- remote: **yes**
	- local: **yes**
	- snapshots & hyper backup
- flow
	- no flow, final stage
- suggestion
	- consume Showroom as External Library in the Immich

### Archive

Archival of all of the photos, used or not used to the Showroom.

```
/.../<ARCHIVE>/
	<YEAR>/
		<ALBUM>/
			<DEVICE>/
				PHOTOS/
				VIDEOS/
```

- input
	- moved files from Darkroom into Archive
- location: NAS
- definitions
	- `ARCHIVE` - Archive directory
- backup
	- remote: **yes**
	- local: **yes**
	- snapshots & hyper backup
- flow
	- no flow, final stage
