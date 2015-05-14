
Documentation for how to use 'smasher', the taxonomy combiner.

See file doc/scripting.md for documentation on using the scripting features of smasher for building, subsetting, querying and other operations on taxonomies. 

See file doc/README.md for release notes for the taxonomy itself.

Taxonomies are represented as directories, see 
[here](https://github.com/OpenTreeOfLife/reference-taxonomy/wiki/Interim-taxonomy-file-format).

To test to see whether you can run Smasher, do 'make aster'.

To create a new version of OTT:

- Put previous version in tax/prev_ott/ .  The taxonomy file name
  should be taxonomy.tsv, similarly synonyms.tsv and so on.  (Around version 2.2
  the file names changed from no extension to a .tsv extension.)
  The purpose of prev_ott is to get continuity of identifier assignments.

- Edit definition of WHICH in Makefile to be new version number, e.g.
  WHICH=2.7.draft13

- To refresh NCBI, rm -rf tax/ncbi.  Similarly GBIF and Silva.
  (Note that GBIF is being updated very infrequently,
  so refreshing it is sort of a waste of time.  Silva is updated 
  every few months, I think.)

- 'make'

- Result will be in tax/ott/

- Simple quality control check: do 'make short-list.tsv' - this will show you 
  taxa have three properties: (1) are used in study OTUs, (2) are deprecated 
  in this version of OTT 2.3, (3) have no replacement taxon id.

To make taxonomies in general:

- Run Smasher.  Command lines arguments are input taxonomies and
  operations to be performed.  See 'nem' and 'ott' targets for
  examples.  Taxonomy specifiers must end in /.  Some operations:

    --edits <dir>      specifies the location of directory full of edit files

    --ids <tax>/     specifies a taxonomy from which identifiers will be
      	  	     drawn for reuse (usually the previous version of whatever it is
      		     you're building)

   --aux <preottol>/     force generation of preottol mapping

Taxonomies can also be specified as Newick strings (not ending in /),
for testing purposes.

If you're puzzled by some decision the algorithm has made, it might be
helpful to look at the log.tsv file.
