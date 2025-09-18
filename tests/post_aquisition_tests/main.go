package main

import (
	"fmt"
	"os"
	"path/filepath"
	"time"
)

func main() {
	home, err := os.UserHomeDir()
	if err != nil {
		fmt.Println("Error finding home directory:", err)
		os.Exit(1)
	}

	desktop := filepath.Join(home, "Desktop")
	logFile := filepath.Join(desktop, "biobeamer_test.log")

	// Only create/write if the file does not exist
	if _, err := os.Stat(logFile); os.IsNotExist(err) {
		now := time.Now().Format("2006-01-02 15:04:05")
		if err := os.WriteFile(logFile, []byte(now+"\n"), 0644); err != nil {
			fmt.Println("Error writing file:", err)
			os.Exit(1)
		}
		fmt.Println("Created:", logFile)
	} else if err != nil {
		fmt.Println("Error checking file:", err)
		os.Exit(1)
	} else {
		fmt.Println("File already exists:", logFile)
	}
}

