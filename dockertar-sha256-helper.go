package main

import (
	"fmt"
	"compress/gzip"
	"os"
	"io"
	"crypto/sha256"
)

func main() {
	reader, err := os.Open(os.Args[1])
	if err != nil {
		os.Exit(1)
	}
	buf := make([]byte, 4096)
	sha_256 := sha256.New()
	w := gzip.NewWriter(sha_256)

	for {
		n, err := reader.Read(buf)
		if n > 0 {
			w.Write(buf[:n])
		}
		if err == io.EOF {
			break
		}
		if err != nil {
			panic(err)
		}
	}
	w.Close()

	fmt.Printf("%x\n", sha_256.Sum(nil))
}
