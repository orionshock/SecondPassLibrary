$since = "midnight"

Write-Host "`nToday's commits:`n"

git --no-pager log --since="$since" --stat --pretty=format:"commit %H%nAuthor: %an <%ae>%nDate:   %ad%n%n    %s%n%n%b" --date=iso-local

Write-Host "`nToday's totals:`n"

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
$commits = git rev-list --count --since="$since" HEAD

Write-Host "Commits: $commits"
Write-Host "Added:   $added"
Write-Host "Deleted: $deleted"
Write-Host "Net:     $net"
