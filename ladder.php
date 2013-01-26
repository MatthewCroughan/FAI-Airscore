<?php
require_once 'authorisation.php';
require_once 'format.php';
require 'hc.php';

function hcincludedcomps($link,$ladPk)
{
    echo "<h1><span>Included Competitions</span></h1>";
    $sql = "select C.* from tblLadderComp LC, tblCompetition C where LC.comPk=C.comPk and ladPk=$ladPk order by comDateTo";
    $result = mysql_query($sql,$link);
    $comps = array();
    while($row = mysql_fetch_array($result))
    {
        // FIX: if not finished & no tracks then submit_track page ..
        // FIX: if finished no tracks don't list!
        $cpk = $row['comPk'];
        $comps[] = "<a href=\"comp_result.php?comPk=$cpk\">" . $row['comName'] . "</a>";
    }
    echo fnl($comps);
}
function taskcmp($a, $b)
{
    if (!is_array($a)) return 0;
    if (!is_array($b)) return 0;

    if ($a['tname'] == $b['tname']) 
    {
        return 0;
    }
    return ($a['tname'] < $b['tname']) ? -1 : 1;
}

function add_result(&$results, $row, $topnat, $how)
{
    $score = round($row['ladScore'] / $topnat);
    $validity = $row['tasQuality'] * 1000;
    $pilPk = $row['pilPk'];
    // $row['tasName'];
    $tasName = substr($row['comName'], 0, 2) . ' ' . substr($row['comDateTo'],0,4);
    $fullName = substr($row['comName'], 0, 2) . substr($row['comDateTo'],2,2) . '&nbsp;' . substr($row['tasName'],0,1) . substr($row['tasName'], -1, 1);

    if (!array_key_exists($pilPk,$results) || !$results[$pilPk])
    {
        $results[$pilPk] = array();
        $results[$pilPk]['name'] = $row['pilFirstName'] . ' ' . $row['pilLastName'];
        $results[$pilPk]['hgfa'] = $row['pilHGFA'];
        //$results[$pilPk]['civl'] = $civlnum;
    }
    //echo "pilPk=$pilPk tasname=$tasName, result=$score<br>\n";
    $perf = 0;
    if ($how == 'ftv') 
    {
        $perf = 0;
        if ($validity > 0)
        {
            $perf = round($score / $validity, 3) * 1000;
        }
    }
    else
    {
        $perf = round($score, 0);
    }

    if ($perf >= 1)
    {
        $results[$pilPk]["${perf}${fullName}"] = array('score' => $score, 'validity' => $validity, 'tname' => $fullName, 'taspk' => $row['tasPk'], 'extpk' => 0 + $row['extPk']);
    }

    return "${perf}${fullName}";
}

function ladder_result($ladPk, $ladder, $restrict)
{
    $start = $ladder['ladStart'];
    $end = $ladder['ladEnd'];
    $how = $ladder['ladHow'];
    $nat = $ladder['ladNationCode'];
    $ladParam = $ladder['ladParam'];

    $topnat = array();
    $sql = "select T.tasPk, max(T.tarScore) as topNat 
            from tblTaskResult T, tblTrack TL, tblPilot P
            where T.traPk=TL.traPk and TL.pilPk=P.pilPk and P.pilNationCode='$nat'
            group by tasPk";
    $result = mysql_query($sql) or die('Top National Query: ' . mysql_error());
    while ($row = mysql_fetch_array($result, MYSQL_ASSOC))
    {
        $topnat[$row['tasPk']] = $row['topNat'];
    }

    // Select from the main database of results
    $sql = "select TR.tarScore,
        TP.pilPk, TP.pilLastName, TP.pilFirstName, TP.pilNationCode, TP.pilHGFA, TP.pilSex,
        TK.tasPk, TK.tasName, TK.tasDate, TK.tasQuality, 
        C.comName, C.comDateTo, LC.lcValue, 
        case when date_sub('$end', INTERVAL 365 DAY) > C.comDateTo 
        then (TR.tarScore * LC.lcValue * 0.90 * TK.tasQuality) 
        else (TR.tarScore * LC.lcValue * TK.tasQuality) end as ladScore, 
        (TR.tarScore * LC.lcValue * (case when date_sub('$end', INTERVAL 365 DAY) > C.comDateTo 
            then 0.90 else 1.0 end) / (TK.tasQuality * LC.lcValue)) as validity
from    tblLadderComp LC 
        join tblLadder L on L.ladPk=LC.ladPk
        join tblCompetition C on LC.comPk=C.comPk
        join tblTask TK on C.comPk=TK.comPk
        join tblTaskResult TR on TR.tasPk=TK.tasPk
        join tblTrack TT on TT.traPk=TR.traPk
        join tblPilot TP on TP.pilPk=TT.pilPk
WHERE LC.ladPk=$ladPk and TK.tasDate > '$start' and TK.tasDate < '$end'
    and TP.pilNationCode=L.ladNationCode $restrict
    order by TP.pilPk, C.comPk, (TR.tarScore * LC.lcValue * TK.tasQuality) desc";

    $result = mysql_query($sql) or die('Ladder query failed: ' . mysql_error());
    $results = array();
    while ($row = mysql_fetch_array($result, MYSQL_ASSOC))
    {
        add_result($results, $row, $topnat[$row['tasPk']], $how);
    }

    // Work out how much validity we want (not really generic)
    $sql = "select sum(tasQuality)*1000 from tblLadderComp LC 
        join tblLadder L on L.ladPk=LC.ladPk and LC.lcValue=450
        join tblCompetition C on LC.comPk=C.comPk
        join tblTask TK on C.comPk=TK.comPk
        WHERE LC.ladPk=$ladPk and TK.tasDate > '$start' and TK.tasDate < '$end'";

    $result = mysql_query($sql) or die('Total quality query failed: ' . mysql_error());
    $param = mysql_result($result,0,0) * $ladParam / 100 ;

    // Add external task results (to 1/3 of validity)
    if ($ladder['ladIncExternal'] > 0)
    {
        $sql = "select TK.extPk, TK.extURL as tasPk,
        TP.pilPk, TP.pilLastName, TP.pilFirstName, TP.pilNationCode, TP.pilHGFA, TP.pilSex,
        TK.tasName, TK.tasQuality, TK.comName, TK.comDateTo, TK.lcValue, TK.tasTopScore,
        case when date_sub('$end', INTERVAL 365 DAY) > TK.comDateTo 
        then (ER.etrScore * TK.lcValue * 0.90 * TK.tasQuality) 
        else (ER.etrScore * TK.lcValue * TK.tasQuality) end as ladScore, 
        (ER.etrScore * TK.lcValue * (case when date_sub('$end', INTERVAL 365 DAY) > TK.comDateTo 
            then 0.90 else 1.0 end) / (TK.tasQuality * TK.lcValue)) as validity
        from tblExtTask TK
        join tblExtResult ER on ER.extPk=TK.extPk
        join tblPilot TP on TP.pilPk=ER.pilPk
WHERE TK.comDateTo > '$start' and TK.comDateTo < '$end'
        $restrict
        order by TP.pilPk, TK.extPk, (ER.etrScore * TK.lcValue * TK.tasQuality) desc";
        $result = mysql_query($sql) or die('Ladder query failed: ' . mysql_error());
        while ($row = mysql_fetch_array($result, MYSQL_ASSOC))
        {
            $res = add_result($results, $row, $row['tasTopScore'], $how);
        }

        return filter_results($ladPk, $how, $param, $param * 0.33, $results);
    }

    return filter_results($ladPk, $how, $param, 0, $results);
}

function filter_results($ladPk, $how, $param, $extpar, $results)
{
    // Do the scoring totals (FTV/X or Y tasks etc)
    $sorted = array();
    foreach ($results as $pil => $arr)
    {
        krsort($arr, SORT_NUMERIC);

        $pilscore = 0;
        if ($how != 'ftv')
        {
            # Max rounds scoring
            $count = 0;
            foreach ($arr as $perf => $taskresult)
            {
                //if ($perf == 'name') 
                if (ctype_alpha($perf))
                {
                    continue;
                }
                if ($count < $param)
                {
                    $arr[$perf]['perc'] = 100;
                    $pilscore = $pilscore + $taskresult['score'];
                }
                else
                {
                    $arr[$perf]['perc'] = 0;
                }
                $count++;
                
            }
        }
        else
        {
            # FTV scoring
            $pilvalid = 0;
            $pilext = 0;
            foreach ($arr as $perf => $taskresult)
            {
                //if ($perf == 'name') 
                if (ctype_alpha($perf))
                {
                    continue;
                }

                //echo "pil=$pil perf=$perf valid=", $taskresult['validity'], " score=", $taskresult['score'], "<br>";
                if ($pilvalid < $param)
                {
                    // if external
                    if ((0+$taskresult['extpk'] > 0) && ($pilext < $extpar)) 
                    {
                        $gap = $extpar - $pilext;
                        if ($gap > $param - $pilvalid)
                        {
                          $gap = $param - $pilvalid;
                        }
                        $perc = 0;
                        if ($taskresult['validity'] > 0)
                        {
                            $perc = $gap / $taskresult['validity'];
                        }
                        if ($perc > 1)
                        {
                            $perc = 1;
                        }
                        $pilext = $pilext + $taskresult['validity'] * $perc;
                        $pilvalid = $pilvalid + $taskresult['validity'] * $perc;
                        $pilscore = $pilscore + $taskresult['score'] * $perc;
                        $arr[$perf]['perc'] = $perc * 100;
                    }
                    else
                    {
                        $gap = $param - $pilvalid;
                        $perc = 0;
                        if ($taskresult['validity'] > 0)
                        {
                            $perc = $gap / $taskresult['validity'];
                        }
                        if ($perc > 1)
                        {
                            $perc = 1;
                        }
                        $pilvalid = $pilvalid + $taskresult['validity'] * $perc;
                        $pilscore = $pilscore + $taskresult['score'] * $perc;
                        $arr[$perf]['perc'] = $perc * 100;
                    }
                }
            }   
        }

        // resort arr by task?
        //uasort($arr, "taskcmp");
        #echo "pil=$pil pilscore=$pilscore<br>";

        foreach ($arr as $key => $res)
        {
            #echo "key=$key<br>";
            #if ($key != 'name')
            if (ctype_digit(substr($key,0,1)))
            {
                $arr[$res['tname']] = $res;
                unset($arr[$key]);
            }
        }
        $pilscore = round($pilscore,0);
        $sorted["${pilscore}!${pil}"] = $arr;
    }

    krsort($sorted, SORT_NUMERIC);
    //var_dump($sorted);
    return $sorted;
}

//
// Main Body Here
//

$ladPk = reqival('ladPk');
$start = reqival('start');
$class = reqsval('class');
if ($start < 0)
{
    $start = 0;
}
$link = db_connect();
$title = 'highcloud.net';

$query = "SELECT L.* from tblLadder L where ladPk=$ladPk";
$result = mysql_query($query) or die('Ladder query failed: ' . mysql_error());
$row = mysql_fetch_array($result, MYSQL_ASSOC);
if ($row)
{
    $ladName = $row['ladName'];
    $title = $ladName;
    $ladder = $row;
}


$fdhv= '';
$classstr = '';
if (array_key_exists('class', $_REQUEST))
{
    $cval = intval($_REQUEST['class']);
    if ($comClass == "HG")
    {
        $carr = array ( "'floater'", "'kingpost'", "'open'", "'rigid'"       );
        $cstr = array ( "Floater", "Kingpost", "Open", "Rigid", "Women", "Seniors", "Juniors" );
    }
    else
    {
        $carr = array ( "'1/2'", "'2'", "'2/3'", "'competition'"       );
        $cstr = array ( "Fun", "Sport", "Serial", "Open", "Women", "Seniors", "Juniors" );
    }
    $classstr = "<b>" . $cstr[intval($_REQUEST['class'])] . "</b> - ";
    if ($cval == 4)
    {
        $fdhv = "and TP.pilSex='F'";
    }
    else
    {
        $fdhv = $carr[intval($_REQUEST['class'])];
        $fdhv = "and TT.traDHV<=$fdhv ";
    }
}

hcheader($title, 2, "$classstr $comDateFrom - $comDateTo");

echo "<div id=\"content\">";
//echo "<div id=\"text\" style=\"overflow: auto; max-width: 600px;\">";
echo "<div id=\"text\" style=\"overflow: auto;\">";

//echo "<h1>Details</h1>";
// Determine scoring params / details ..

$tasTotal = 0;
$query = "select count(*) from tblTask where comPk=$comPk";
$result = mysql_query($query); // or die('Task total failed: ' . mysql_error());
if ($result)
{
    $tasTotal = mysql_result($result, 0, 0);
}
if ($comOverall == 'all')
{
    # total # of tasks
    $comOverallParam = $tasTotal;
    $overstr = "All rounds";
}
else if ($comOverall == 'round')
{
    $overstr = "$comOverallParam rounds";
}
else if ($comOverall == 'round-perc')
{
    $comOverallParam = round($tasTotal * $comOverallParam / 100, 0);
    $overstr = "$comOverallParam rounds";
}
else if ($comOverall == 'ftv')
{
    $sql = "select sum(tasQuality) as totValidity from tblTask where comPk=$comPk";
    $result = mysql_query($sql) or die('Task validity query failed: ' . mysql_error());
    $totalvalidity = round(mysql_result($result, 0, 0) * $comOverallParam * 10,0);
    $overstr = "FTV $comOverallParam% ($totalvalidity pts)";
    $comOverallParam = $totalvalidity;
}


$today = getdate();
$tdate = sprintf("%04d-%02d-%02d", $today['year'], $today['mon'], $today['mday']);

$rtable = array();
$rdec = array();

if ($comClass == "HG")
{
    $classopts = array ( 'open' => '', 'floater' => '&class=0', 'kingpost' => '&class=1', 
        'hg-open' => '&class=2', 'rigid' => '&class=3', 'women' => '&class=4' );
}
else
{
    $classopts = array ( 'open' => '', 'fun' => '&class=0', 'sports' => '&class=1', 
        'serial' => '&class=2', 'women' => '&class=4' );
}
$cind = '';
if ($class != '')
{
    $cind = "&class=$class";
}
$copts = array();
foreach ($classopts as $text => $url)
{
    $copts[$text] = "ladder.php?ladPk=$ladPk$url";
}

$rdec[] = 'class="h"';
$rdec[] = 'class="h"';
$hdr = array( fb('Res'),  fselect('class', "ladder.php?ladPk=$ladPk$cind", $copts, ' onchange="document.location.href=this.value"'), fb('HGFA'), fb('Total') );
$hdr2 = array( '', '', '', '' );

# find each task details
$alltasks = array();
$taskinfo = array();
$sorted = array();

$sorted = ladder_result($ladPk, $ladder, $fdhv);
$subtask = '';

$rtable[] = $hdr;
$rtable[] = $hdr2;

$lasttot = 0;
$count = 1;
foreach ($sorted as $pil => $arr)
{
    $nxt = array();
    if ($count % 2)
    {
        $rdec[] = 'class="d"';
    }
    else
    {
        $rdec[] = 'class="l"';
    }
    $tot = 0 + $pil;
    if ($tot != $lasttot)
    {
        $nxt[] = $count;
        $nxt[] = $arr['name'];
    }
    else
    {
        $nxt[] = '';
        $nxt[] = $arr['name'];
    }

    $nxt[] = $arr['hgfa'];
    $nxt[] = fb($tot);
    $lasttot = $tot;

    //if (ctype_digit(substr($key,0,1)))
    foreach ($arr as $key => $sarr)
    { 
        $score = 0;
        $perc = 100;
        if (array_key_exists('score', $sarr))
        {
            $score = $sarr['score'];
            $tname = $sarr['tname'];
            $tpk = $sarr['taspk'];
            $perc = round($sarr['perc'], 0);
            if (!$score)
            {
                $score = 0;
            }
            if ($perc == 100)
            {
                if ($tpk > 0)
                {
                    $nxt[] = "<a href=\"task_result.php?tasPk=$tpk\">$tname $score</a>";
                }
                else
                {
                    $nxt[] = "<a href=\"$tpk\">$tname $score</a>";
                }
            }
            else if ($perc > 0)
            {
                if ($tpk > 0)
                {
                    $nxt[] = "<a href=\"task_result.php?tasPk=$tpk\">$tname $score $perc%</a>";
                }
                else
                {
                    $nxt[] = "<a href=\"$tpk\">$tname $score $perc%</a>";
                }
            }
            else
            {
                //$nxt[] = "<del>$tname $score</del>";
            }
        }
    }
    $rtable[] = $nxt;
    $count++;
}
echo ftable($rtable, "border=\"0\" cellpadding=\"3\" alternate-colours=\"yes\" align=\"center\"", $rdec, '');

//echo "</table>";
if ($ladder['ladHow'] == 'ftv')
{
    echo "1. Click <a href=\"ftv.php?comPk=$comPk\">here</a> for an explanation of FTV<br>";
    echo "2. Highlighted scores 100%, or indicated %, other scores not included<br>";
}

if ($embed == '')
{
    // Only emit image if results table is "narrow"
    echo "</div>";
    echo "<div id=\"sideBar\">";

    echo "<h1>Ladder Details</h1>";
    $detarr = array(
        array("<b>Ladder</b> ", "<i>$ladName</i>"),
        array ("<b>Nation</b> ", "<i>" . $ladder['ladNationCode'] . "</i>"),
        array ("<b>Method</b> ", "<i>" . $ladder['ladHow'] . ' ' . $ladder['ladParam'] .  "</i>"),
        array("<i>" . $ladder['ladStart'] . "</i>",  "<i>" . $ladder['ladEnd'] . "</i>")
    );

    echo ftable($detarr, 'border="0" cellpadding="0" width="185"', '', array('', 'align="right"'));
    hcincludedcomps($link,$ladPk);
    //hcclosedcomps($link);
    echo "</div>";
    //if (sizeof($taskinfo) > 8)
    //{
    //    echo "<div id=\"image\" background=\"images/pilots.jpg\"></div>";
    //}
    //else
    {
        hcimage($link,$comPk);
    }
    hcfooter();
}
?>
</body>
</html>

