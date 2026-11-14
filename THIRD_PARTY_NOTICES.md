# Third-party notices and provenance

The repository-level MIT license applies to original kit tooling and documentation. It does **not** relicense the PHP-derived cumulative patch or downloaded upstream sources.

| Material | Origin | Applicable notices |
|---|---|---|
| `patches/build007.patch`, PHP portions | PHP source and local backport work | [PHP License 3.01](licenses/PHP-3.01.txt) |
| Zend portions of the patch | Zend Engine in PHP | [Zend Engine License 2.00](licenses/Zend-Engine-2.00.txt) |
| date-library portions | timelib within PHP | Expat; original authors/terms in [Ubuntu source copyright inventory](licenses/Ubuntu-PHP-copyright.txt) |
| source reconstruction inputs | Ubuntu PHP source package `.16` | PHP, Zend, Expat and bundled component terms mapped in the same inventory |
| FPM and TSRM source | original PHP distribution | [FPM](licenses/FPM.txt), [TSRM](licenses/TSRM.txt) |

The cumulative backport derives from upstream [01a40e89fbfc499936e3b05888d8f00bfde886df](https://github.com/php/php-src/commit/01a40e89fbfc499936e3b05888d8f00bfde886df), authored by **Arnaud Le Blanc**, with upstream coauthors **Ilija Tovilo, Jakub Zelenka, Nora Dossche and Nicolas Grekas**. Local PHP 7.0 adaptations and subsequent correctness changes are maintained separately by Two Weeks Team. No upstream certification or vendor endorsement is implied.

Earlier minimal-backport research included Freexian work attributed to Arnaud Le Blanc, Ilija Tovilo, Guilhem Moulin and Markus Koschany. That minimal patch is **not** the cumulative build007 patch shipped here. The old experimental implementation and its private operational records are not distributed.

Official source archive pins are in [provenance/inputs.json](provenance/inputs.json). Reconstructed source retains its complete license files; this kit does not replace them. If redistributing a locally built binary, inventory its linked/bundled components and satisfy their terms. This source release does not bundle third-party shared libraries.

This product includes PHP software, freely available from <http://www.php.net/software/>.

This product includes the Zend Engine, freely available at <http://www.zend.com>.
