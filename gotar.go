// This source code will generate gotar binary
// which is needed for atomic migrate export and import commands.

package main

import (
	"archive/tar"
	"io"
	"log"
	"os"
	"path"
	"path/filepath"
)

func main() {

	if len(os.Args) < 3 {
		log.Fatalln("Missing arguments")
	}

	if os.Args[1] == "" {
		log.Fatalln("tar flag cannot be empty. Please use -cf for creation or -xf for extraction")
	}

	if os.Args[1] != "-cf" && os.Args[1] != "-xf" {
		log.Fatalf("%s is not a valid tar flag\n", os.Args[1])
	}

	if os.Args[2] == "" {
		log.Fatalln("Destination filename cannot be empty")
	}

	if os.Args[1] == "-cf" && os.Args[3] == "" {
		log.Fatalln("Source directory cannot be empty")
	}

	tarFlag := os.Args[1]
	destinationFilename := os.Args[2]

	if tarFlag == "-cf" {
		sourceDir := os.Args[3]
		tarDir(destinationFilename, sourceDir)
	} else if tarFlag == "-xf" {
		untarDir(destinationFilename)
	}
}

func checkError(err error) {
	if err != nil {
		log.Fatalln(err)
	}
}

func tarDir(destinationFilename, sourceDir string) {

	if destinationFilename[len(destinationFilename)-3:] != "tar" {
		log.Fatalln("Please provide a valid tar filename")
	}

	tarFile, err := os.Create(destinationFilename)
	checkError(err)

	defer tarFile.Close()

	var fileWriter io.WriteCloser = tarFile
	tarfileWriter := tar.NewWriter(fileWriter)
	defer tarfileWriter.Close()

	walkTar(sourceDir, tarfileWriter)
}

func walkTar(dirPath string, tarfileWriter *tar.Writer) {

	dir, err := os.Open(dirPath)
	checkError(err)

	dirInfo, err := dir.Stat()
	checkError(err)

	// prepare the tar header for dir entry.
	dheader, err := tar.FileInfoHeader(dirInfo, "")
	checkError(err)

	dheader.Name = dir.Name()[1:]

	err = tarfileWriter.WriteHeader(dheader)
	checkError(err)

	files, err := dir.Readdir(0) // grab the files list
	checkError(err)

	for _, fileInfo := range files {
		if fileInfo.IsDir() {
			walkTar(path.Join(dir.Name(), fileInfo.Name()), tarfileWriter)

		} else {
			file, err := os.Open(dir.Name() + string(filepath.Separator) + fileInfo.Name())
			checkError(err)

			defer file.Close()

			// prepare the tar header for file entry.

			header, err := tar.FileInfoHeader(fileInfo, "")
			checkError(err)

			header.Name = file.Name()[1:]

			err = tarfileWriter.WriteHeader(header)
			checkError(err)

			_, err = io.Copy(tarfileWriter, file)
			checkError(err)
		}
	}
}

func untarDir(destinationFilename string) {

	var fileReader io.ReadCloser

	if destinationFilename == "-" {
		fileReader = os.Stdin
	} else {
		if destinationFilename[len(destinationFilename)-3:] != "tar" {
			log.Fatalln("Please provide a valid tar filename")
		}

		file, err := os.Open(destinationFilename)
		checkError(err)
		defer file.Close()

		fileReader = file
	}

	tarfileReader := tar.NewReader(fileReader)
	pwd, err := os.Getwd()
	checkError(err)

	for {
		header, err := tarfileReader.Next()
		if err != nil {
			if err == io.EOF {
				break
			}
			log.Fatalln(err)
		}

		fileInfo := header.FileInfo()

		if fileInfo.IsDir() {
			err = os.MkdirAll(path.Join(pwd, header.Name), fileInfo.Mode())
			checkError(err)
		} else {
			tarFile, err := os.Create(path.Join(pwd, header.Name))
			checkError(err)
			defer tarFile.Close()

			_, err = io.Copy(tarFile, tarfileReader)
			checkError(err)
		}

	}
}
