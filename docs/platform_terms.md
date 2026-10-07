# Platform terms review (Q-35)

These are the terms that apply when VoxShift processes rights-cleared footage and consented voices on Kaggle, and when it obtains footage. Owner decision: D-81.

- **Read:** 2026-10-07 by a research subagent (read-only), reviewed by the main agent. "V" means the text was read in the primary source; "R" means it is reported second-hand.
- **Kaggle pages:** they render only in a browser, so they were read through a rendering reader.
- **Not legal advice.** Items marked **Review** need the owner's explicit decision.
- **Versions read:**
  - Kaggle Terms of Use: no effective date shown;
  - Kaggle Privacy Policy: 5 Feb 2024;
  - Kaggle Acceptable Use Policy: 22 Jun 2025;
  - Kaggle Community Guidelines: 4 Mar 2026;
  - YouTube Terms of Service: 15 Dec 2023, US English.
- Save dated copies before relying on them; terms change.

## Kaggle

| Topic | What the terms say | Source | V/R | Consequence for VoxShift |
| --- | --- | --- | --- | --- |
| Permitted use | "only use the Services for your own internal, personal, non-commercial use, and not on behalf of or for the benefit of any third party" (§3) | [Terms](https://www.kaggle.com/terms) | V | Fits personal R&D (D-61). **Review** if the project becomes commercial, employer-related or done for someone else. |
| Accounts | One active account per person; never share accounts (§3) | Terms | V | Never use contributors' accounts or a second account for extra quota. |
| Compute use | No cryptomining, no server farming, no "activity unrelated to ML data science"; abuse of free resources leads to a ban | [AUP](https://www.kaggle.com/aup), [Guidelines](https://www.kaggle.com/community-guidelines) | V | Keep notebooks to ML evaluation. |
| Other Google services | Do not use Kaggle to access another Google product in breach of that product's terms | AUP | V | **Never run a downloader (yt-dlp) inside Kaggle.** |
| License to Kaggle | Uploads grant Kaggle a "royalty-free, perpetual, irrevocable, and worldwide" license to operate the service. Private uploads get an additional, narrower grant, which does not replace the general one (§9). | Terms | V | Covers the voice recordings too. **Review:** the consent note must say so. |
| Collaborators | Sharing grants collaborators rights in the content (§9) | Terms | V | Keep datasets and notebooks owner-only. |
| Warranty | You warrant you hold all necessary rights and indemnify Kaggle (§5, §6, §15) | Terms | V | All rights risk sits with the owner. |
| Who sees private data | Private data is visible to you, your collaborators, "and to Kaggle for purposes consistent with the Kaggle Privacy Policy". Content is analysed for abuse, private or public. | [Datasets docs](https://www.kaggle.com/docs/datasets), [Privacy](https://www.kaggle.com/privacy) | V | Kaggle may view private uploads, through people or machines. |
| Notebook versions | A version stores code, logs, outputs and data sources. Nothing found on whether deleting a dataset removes notebook versions or outputs. | [Notebooks docs](https://www.kaggle.com/docs/notebooks) | V | Delete notebooks and all their versions, not only datasets. Never print transcripts (logs are stored). |
| Product use | Uploaded content may be used "to improve our services and to develop new products". The policy says nothing explicit either way about training models on uploads. | Privacy | V | **Review:** say so in the consent note. |
| Deletion | Takes "around 2 months", plus up to 1 month of recovery and up to 6 months in backups. Some data is kept for legal or business reasons, and anonymised aggregates may remain. | Privacy | V | "Delete after each run" starts deletion; it is not immediate. |
| Location | Data "may be processed on servers located outside of the country where you live" | Privacy | V | Cross-border processing. **Review** against the contributors' local data-protection law (for example GDPR or Turkey's KVKK). |
| Biometric / voice data | Not mentioned in the Terms or the Privacy Policy. The AUP forbids uploads that violate others' privacy rights. No data processing agreement found for free accounts. | Terms, Privacy, AUP | V (absence) | Kaggle offers no consent mechanism; consent is entirely the owner's responsibility. **Review.** |

## Footage sources

| Topic | What the terms say | Source | V/R | Consequence for VoxShift |
| --- | --- | --- | --- | --- |
| YouTube downloads | Users may not "access, reproduce, download … any Content except (a) as expressly authorized by the Service; or (b) with prior written permission from YouTube and, if applicable, the respective rights holders". It also bans automated means and circumventing copy restrictions. | [YouTube ToS](https://www.youtube.com/static?template=terms) | V | **Review:** the three S3 films were downloaded with yt-dlp, which neither (a) nor (b) covers on its face. |
| CC license vs site terms | "if you download CC-licensed material from a site that does not permit downloading, you may be breaking the terms of use of the site, but you are not infringing the CC license" | [CC FAQ](https://creativecommons.org/faq/) | V | CC-BY settles copyright, not the platform agreement. |
| Sanctioned routes | Wikimedia Commons (free reuse, per-file license); Vimeo, where the owner enabled downloads; files obtained directly from the creator | [Commons](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia), [Vimeo help](https://help.vimeo.com/hc/en-us/articles/12426502581265-How-to-download-a-video-on-Vimeo) | V | Preferred for new golden clips. A Vimeo download button is not a license; check each license. |
| People in the films | CC BY 4.0 does not license "publicity, privacy, and/or other similar personality rights" (§2(b)(1)) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.en) | V | Cloning the actors' voices is not covered by CC-BY. This matches `docs/footage.md`: private evaluation only, never published. **Review.** |
| Sublicensing | CC licenses do not let you license a platform over CC content you do not own; Kaggle §9 asks for a license over every upload | CC FAQ, Kaggle Terms | V | Unresolved tension when CC footage is uploaded to Kaggle. **Review.** |
| Attribution | CC-BY duties apply when sharing publicly, including a notice that the work was modified | CC BY 4.0 | V | Private use: keep the records (`docs/footage.md`). Any public clip or screenshot of a dub needs attribution and a "modified" notice. |

## Needs explicit owner review

1. **The yt-dlp downloads** of the three S3 films, against YouTube ToS items 1–3. Options:
   - re-obtain the films through a sanctioned route;
   - ask the creators for the files or for permission;
   - delete the copies.
   The copies are in `media/` and in the private Kaggle dataset `voxshift-s3-clips`.
2. **Golden-clip sourcing:** use only sanctioned routes (Commons, Vimeo downloads, or creator-provided files), never yt-dlp, and never a downloader inside Kaggle.
3. **Actors' voices:** dubbing tests clone the film actors' voices, and CC-BY does not cover that. Keep outputs private (as today), or get the actors' consent.
4. **CC footage on Kaggle:** Kaggle's §9 license conflicts with CC's no-sublicensing rule.
5. **Consent for voice contributors** must cover Kaggle (checklist below).
6. **Deletion:** delete datasets, notebooks and every notebook version. Expect about 2 months before data is gone, and up to 6 months in backups.
7. **Contributors' local law** (cross-border processing, voice as biometric data), since Kaggle's terms do not address it.
8. **Status change:** recheck all of this if VoxShift stops being personal, non-commercial R&D.

## Consent note for voice contributors (checklist)

- [ ] Recordings and derived files (cloned speech, embeddings, logs) are uploaded to Kaggle (Google) and processed there, possibly outside the contributor's country.
- [ ] Purpose: private, non-commercial R&D evaluation. Nothing is published and no collaborators are added.
- [ ] Kaggle receives a royalty-free, perpetual, irrevocable, worldwide license to operate its service over the uploaded files.
- [ ] Kaggle may view private data and check it for abuse, and its policy does not exclude use for product development.
- [ ] Deletion happens after each run, but Kaggle takes about 2 months, keeps backups for up to 6 months, and may retain some data longer.
- [ ] How to withdraw consent, and what happens to data already uploaded.
- [ ] The dates of the Kaggle documents referred to, plus the date and signature.

Consent notes are kept outside git (D-74).
