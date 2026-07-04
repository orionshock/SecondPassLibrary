$since = "midnight"

Write-Host "`nToday's commits with LOC summary:`n"

git --no-pager log --since="$since" --shortstat --pretty=format:"%h %ad %an %s" --date=short

Write-Host "`nTotal LOC changes today:`n"

$stats = git --no-pager log --since="$since" --numstat --pretty=format:"" |
  Where-Object { $_ -match '^\d+\s+\d+\s+' } |
  ForEach-Object {
    $parts = $_ -split '\s+'

    [pscustomobject]@{
      Added   = [int]$parts[0]
      Deleted = [int]$parts[1]
    }
  }

$added = ($stats | Measure-Object Added -Sum).Sum
$deleted = ($stats | Measure-Object Deleted -Sum).Sum

if ($null -eq $added) { $added = 0 }
if ($null -eq $deleted) { $deleted = 0 }

$net = $added - $deleted

Write-Host "Added:   $added"
Write-Host "Deleted: $deleted"
Write-Host "Net:     $net"