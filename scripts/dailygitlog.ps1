param(
  [Parameter(Position = 0)]
  [ValidateRange(0, 3650)]
  [int]$PreviousDays = 0
)

$today = (Get-Date).Date

for ($dayOffset = 0; $dayOffset -le $PreviousDays; $dayOffset++) {
  $day = $today.AddDays(-$dayOffset)
  $nextDay = $day.AddDays(1)
  $since = $day.ToString('yyyy-MM-ddTHH:mm:sszzz')
  $before = $nextDay.ToString('yyyy-MM-ddTHH:mm:sszzz')
  $dayLabel = if ($dayOffset -eq 0) { "Today ($($day.ToString('yyyy-MM-dd')))" } else { $day.ToString('dddd, yyyy-MM-dd') }

  if ($dayOffset -gt 0) {
    Write-Output "`n$('=' * 72)"
  }

  Write-Output "`n$dayLabel commits:`n"

  git --no-pager log "--since=$since" "--before=$before" --stat --pretty=format:"commit %H%nAuthor: %an <%ae>%nDate:   %ad%n%n    %s%n%n%b" --date=iso-local

  Write-Output "`n`n$dayLabel totals:`n"

  $stats = git --no-pager log "--since=$since" "--before=$before" --numstat --pretty=format:"" |
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
  $commits = git rev-list --count "--since=$since" "--before=$before" HEAD

  Write-Output "Commits: $commits"
  Write-Output "Added:   $added"
  Write-Output "Deleted: $deleted"
  Write-Output "Net:     $net"
}
