if [[ "$OSTYPE" != "msys" && "$OSTYPE" != "win32" ]]; then
  Esc=$(printf "\033")
  ColourReset="${Esc}[m"
  ColourBold="${Esc}[1m"
  Red="${Esc}[31m"
  Green="${Esc}[32m"
  Yellow="${Esc}[33m"
  Blue="${Esc}[34m"
  Magenta="${Esc}[35m"
  Cyan="${Esc}[36m"
  White="${Esc}[37m"
  BoldRed="${Esc}[1;31m"
  BoldBlue="${Esc}[1;90m"
  Reset="${Esc}[0m"  # ANSI code for bright and bold green
fi

current_time=$(date +"%Y-%m-%d %H:%M:%S")


message="
${Yellow}================================================================================
${BoldBlue}    _   ______        ____  ____  ________ __ __________________  __
${BoldBlue}   / | / / __ \      / __ \/ __ \/ ____/ //_// ____/_  __/ __ \ \/ /
${BoldBlue}  /  |/ / / / /_____/ /_/ / / / / /   / ,<  / __/   / / / /_/ /\  / 
${BoldBlue} / /|  / /_/ /_____/ _, _/ /_/ / /___/ /| |/ /___  / / / _, _/ / /  
${BoldBlue}/_/ |_/_____/     /_/ |_|\____/\____/_/ |_/_____/ /_/ /_/ |_| /_/   
${Reset}${Yellow}================================================================================${Reset}
${Green}[Success!] Build completed at: ${current_time}${Reset}
${Reset}${Yellow}================================================================================${Reset}
"

echo -e "$message"
