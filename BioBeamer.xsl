

<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform">


<xsl:template match="/">
<html>

<style type="text/css">
@import url("fcc_config.css");
</style>

<body>
<img src="graphics/BioBeamer.jpg"/> 

	<h1>BioBeamer Configuration</h1>
	<div>
        <p>
	This page gives you the overview where and with what concrete options BioBeamer is configured.
	</p>
	<p>
	If you have any further questions on the converter options, please do not hesitate to let us know.
	Contact: protinf@fgcz.ethz.ch
	</p>
	</div>

	<xsl:apply-templates/> 

	<h1>Statistics</h1>
	<h2>FileSize</h2>
	<img src="graphics/BioBeamer_stat_0.svg" width="320" />
	<h2>Number of files</h2>
	<img src="graphics/BioBeamer_stat_1.svg" width="320" />

	<p>
	source: $HeadURL: http://fgcz-svn.uzh.ch/repos/fgcz/stable/proteomics/config/BioBeamer.xsl $; $Date: 2015-12-22 11:52:13 +0100 (Tue, 22 Dec 2015) $; $Author: cpanse $
	</p>

</body>
</html>

</xsl:template>

<xsl:template match="host">

      <xsl:variable name="hostname" select="@name"/>
      <xsl:variable name="instrument" select="@instrument"/>
      <a name="hostname-{$hostname}">
      <a name="{$instrument}">
      <xsl:variable name="applicationID" select="b-fabric/applicationID"/>

      <h2>BioBeamer @ <xsl:value-of select="$hostname"/> - <a class='value' href="http://fgcz-bfabric.uzh.ch/bfabric/userlab/show-application.html?applicationId={$applicationID}"> <xsl:value-of select="@instrument"/></a></h2>
      </a> 
      </a> 
       
      <table border='1' cellpadding='4' cellspacing='0'>
      <tr>
      <th>parameter</th><th>value</th>
      </tr>
      <tr>
      	<td>
	pattern
      	</td>
      	<td>
	<xsl:value-of select="@pattern"/>
      	</td>
      </tr>
      <tr>
      	<td>
	source_path
      	</td>
      	<td>
	<xsl:value-of select="@source_path"/>
      	</td>
      </tr>
      <tr>
      	<td>
	target_path
      	</td>
      	<td>
	<xsl:value-of select="@target_path"/>
      	</td>
      </tr>
      <tr>
      	<td>
	func_target_mapping
      	</td>
      	<td>
	<xsl:value-of select="@func_target_mapping"/>
      	</td>
      </tr>
      <tr>
      	<td>
	min_time_diff
      	</td>
      	<td>
	<xsl:value-of select="@min_time_diff"/> seconds
      	</td>
      </tr>
      <tr>
      	<td>
	max_time_diff
      	</td>
      	<td>
	<xsl:value-of select="@max_time_diff"/> seconds
      	</td>
      </tr>
      <tr>
      	<td>
	min_size 
      	</td>
      	<td>
	<xsl:value-of select="@min_size"/> Bytes
      	</td>
      </tr>
      <tr>
      	<td>
	robocopy_args
      	</td>
      	<td>
	<xsl:value-of select="@robocopy_args"/> 
      	</td>
      </tr>
      </table>


</xsl:template>
</xsl:stylesheet>

